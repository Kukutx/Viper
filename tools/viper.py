#!/usr/bin/env python3
"""Viper repository checks, inventory and release-integrity tools."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-f]{40}\Z")
VERSION = re.compile(r"\d+\.\d+\.\d+\Z")
ACTION = re.compile(r"^(\s*(?:-\s*)?uses:\s*)([\w.-]+/[\w./-]+)@([^\s#]+)[^\n]*$", re.M)


def run(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def config(root: Path = ROOT) -> dict:
    data = load(root / "configs/toolchain.json")
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported toolchain schema")
    for key in ("rust", "flutter", "dart", "python", "uv", "cmake", "actionlint"):
        if not VERSION.fullmatch(data[key]):
            raise ValueError(f"{key}: an exact stable version is required")
    for key in ("vcpkg", "hbb_common"):
        if not SHA.fullmatch(data[key]["revision"]):
            raise ValueError(f"{key}: full commit SHA required")
    return data


def selectors(data: dict) -> dict[str, str]:
    return {
        "rust-toolchain.toml": '[toolchain]\nchannel = "' + data["rust"] + '"\nprofile = "minimal"\ncomponents = ["rustfmt", "clippy"]\n',
        ".fvmrc": json.dumps({"flutter": data["flutter"]}, indent=2) + "\n",
        ".python-version": data["python"] + "\n",
    }


def versions(root: Path = ROOT, write: bool = False) -> None:
    for path, expected in selectors(config(root)).items():
        file = root / path
        if file.exists() and file.read_text(encoding="utf-8") == expected:
            continue
        if not write:
            raise ValueError(f"Version drift: {path}; run versions --write")
        file.write_text(expected, encoding="utf-8")

    from build_toolchain import sync
    sync(root, write)


def action_text(text: str, lock: dict, write: bool = False) -> str:
    def replace(match: re.Match) -> str:
        name, ref = match[2], match[3]
        repo = "/".join(name.split("/")[:2])
        if repo.startswith("actions-rs/"):
            raise ValueError("Replace retired actions-rs with native cargo/rustup commands")
        if repo not in lock or not SHA.fullmatch(lock[repo]["sha"]):
            raise ValueError(f"Unreviewed action: {name}")
        expected = lock[repo]
        if not write and ref != expected["sha"]:
            raise ValueError(f"Action drift: {name}@{ref}")
        return match[1] + name + "@" + expected["sha"] + " # " + expected["version"]
    return ACTION.sub(replace, text)


def actions(root: Path = ROOT, write: bool = False) -> None:
    lock = load(root / "configs/actions-lock.json")["actions"]
    for file in sorted((root / ".github").rglob("*.y*ml")):
        before = file.read_text(encoding="utf-8")
        after = action_text(before, lock, write)
        if write and after != before:
            file.write_text(after, encoding="utf-8")


def cargo_rows(path: str, data: dict) -> list[dict]:
    result = []
    def visit(table: dict, scope: str = "") -> None:
        for key, value in table.items():
            here = f"{scope}.{key}".strip(".")
            if key in ("dependencies", "dev-dependencies", "build-dependencies"):
                for alias, spec in value.items():
                    item = {"version": spec} if isinstance(spec, str) else spec
                    source = "git" if "git" in item else "path" if "path" in item else "workspace" if item.get("workspace") else "registry"
                    result.append({"ecosystem": "cargo", "file": path, "scope": here, "name": item.get("package", alias), "alias": alias, "source": source, "requirement": item})
            elif isinstance(value, dict):
                visit(value, here)
    visit(data)
    return result


def fetch_latest(key: tuple[str, str]) -> tuple[tuple[str, str], dict]:
    ecosystem, name = key
    url = f"https://crates.io/api/v1/crates/{name}" if ecosystem == "cargo" else f"https://pub.dev/api/packages/{name}"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Viper-dependency-inventory/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
        latest = data["crate"]["max_stable_version"] if ecosystem == "cargo" else data["latest"]["version"]
        return key, {"latest": latest, "source_url": url}
    except (OSError, ValueError, KeyError) as error:
        return key, {"error": str(error), "source_url": url}


def inventory(root: Path = ROOT, latest: bool = False) -> dict:
    import yaml
    rows = []
    paths = run("git", "ls-files", "-z", cwd=root).split("\0")
    manifests = {p for p in paths if p == "Cargo.toml" or p.endswith("/Cargo.toml")}
    if (root / "libs/hbb_common/Cargo.toml").exists():
        manifests.add("libs/hbb_common/Cargo.toml")
    for path in sorted(manifests):
        rows.extend(cargo_rows(path, tomllib.loads((root / path).read_text(encoding="utf-8"))))
    pub = yaml.safe_load((root / "flutter/pubspec.yaml").read_text(encoding="utf-8"))
    for scope in ("dependencies", "dev_dependencies", "dependency_overrides"):
        for name, spec in pub.get(scope, {}).items():
            source = next((s for s in ("sdk", "git", "path") if isinstance(spec, dict) and s in spec), "registry")
            rows.append({"ecosystem": "pub", "file": "flutter/pubspec.yaml", "scope": scope, "name": name, "source": source, "requirement": spec})
    if latest:
        keys = sorted({(r["ecosystem"], r["name"]) for r in rows if r["source"] == "registry"})
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = dict(pool.map(fetch_latest, keys))
        for row in rows:
            if row["source"] == "registry":
                row.update(results[(row["ecosystem"], row["name"])])
    return {"schema_version": 1, "revision": run("git", "rev-parse", "HEAD", cwd=root).strip(), "note": "Declaration inventory, not proof of compatibility or completed upgrades", "dependencies": rows}


def files_in(directory: Path) -> list[Path]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Artifact directory must be a real directory")
    result = []
    for path in sorted(directory.rglob("*"), key=lambda p: p.relative_to(directory).as_posix()):
        if path.is_symlink():
            raise ValueError(f"Symlink not allowed: {path}")
        if path.is_file() and path != directory / "release-manifest.json":
            result.append(path)
        elif not path.is_dir() and path != directory / "release-manifest.json":
            raise ValueError(f"Unsupported artifact: {path}")
    if not result:
        raise ValueError("Empty release")
    return result


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def make_manifest(directory: Path, revision: str) -> dict:
    if not SHA.fullmatch(revision):
        raise ValueError("Full source commit SHA required")
    return {"schema_version": 1, "revision": revision, "artifacts": [{"path": p.relative_to(directory).as_posix(), "bytes": p.stat().st_size, "sha256": file_hash(p)} for p in files_in(directory)]}


def verify_manifest(directory: Path) -> None:
    manifest = load(directory / "release-manifest.json")
    if manifest.get("schema_version") != 1 or not SHA.fullmatch(manifest.get("revision", "")):
        raise ValueError("Invalid release manifest")
    seen = set()
    for artifact in manifest["artifacts"]:
        name = artifact["path"]
        path = PurePosixPath(name)
        if not name or path.is_absolute() or ".." in path.parts or "\\" in name or str(path) != name or name in seen:
            raise ValueError("Unsafe or duplicate artifact path")
        seen.add(name)
    actual = make_manifest(directory, manifest["revision"])
    expected = sorted(manifest["artifacts"], key=lambda item: item["path"])
    if expected != actual["artifacts"]:
        raise ValueError("Artifact list, size or SHA-256 mismatch")


def check(root: Path = ROOT) -> None:
    versions(root)
    from android_toolchain import check as check_android
    check_android(root)
    actions(root)
    paths = run("git", "ls-files", "-z", cwd=root).split("\0")
    if not (root / "agent.md").is_file():
        raise ValueError("Missing agent.md")
    for path in paths:
        if Path(path).name.lower() in ("claude.md", "agents.md"):
            raise ValueError(f"Duplicate agent entrypoint: {path}")
    data = config(root)
    staged = run("git", "ls-files", "--stage", "libs/hbb_common", cwd=root)
    if not staged.startswith("160000 " + data["hbb_common"]["revision"] + " "):
        raise ValueError("hbb_common Gitlink missing or different from policy")
    if not (root / "libs/hbb_common/Cargo.toml").is_file():
        raise ValueError("Initialize submodules: git submodule update --init --recursive")
    baseline = load(root / "vcpkg.json")["vcpkg-configuration"]["default-registry"]["baseline"]
    if baseline != data["vcpkg"]["revision"]:
        raise ValueError("vcpkg baseline drift")
    run("git", "diff", "--check", cwd=root)
    import yaml
    for file in (root / ".github/workflows").glob("*.yml"):
        yaml.load(file.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    print("Repository configuration passed; native builds, signing and deployment are separate checks.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("env")
    for name in ("versions", "actions"):
        sub.add_parser(name).add_argument("--write", action="store_true")
    audit = sub.add_parser("inventory")
    audit.add_argument("--latest", action="store_true")
    audit.add_argument("--output", type=Path, default=ROOT / "tools/.reports/inventory.json")
    release = sub.add_parser("manifest")
    release.add_argument("directory", type=Path)
    release.add_argument("--revision", required=True)
    sub.add_parser("verify").add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check":
            check()
        elif args.command == "env":
            data = config()
            for key in ("rust", "flutter", "dart", "python", "uv", "cmake", "actionlint"):
                print(f"{key.upper()}_VERSION={data[key]}")
            print("VCPKG_COMMIT_ID=" + data["vcpkg"]["revision"])
        elif args.command in ("versions", "actions"):
            {"versions": versions, "actions": actions}[args.command](write=args.write)
        elif args.command == "inventory":
            data = inventory(latest=args.latest)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            print(f"{len(data['dependencies'])} declarations: {args.output}")
            return int(any("error" in row for row in data["dependencies"]))
        elif args.command == "manifest":
            data = make_manifest(args.directory, args.revision)
            (args.directory / "release-manifest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        elif args.command == "verify":
            verify_manifest(args.directory)
            print("Artifact hashes verified. This is NOT signature verification.")
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
