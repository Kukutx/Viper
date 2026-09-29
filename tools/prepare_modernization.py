"""One-shot migration: prepare tested blobs, never move a ref or publish a release."""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
import viper

ROOT = Path(__file__).resolve().parents[1]


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError(f"Anchor count mismatch: {old[:90]!r}")
    return text.replace(old, new)


def edit_job(text, name, change):
    header = f"  {name}:\n"
    start = text.index(header)
    following = re.search(r"^  [A-Za-z0-9_-]+:\s*$", text[start + len(header):], re.M)
    end = start + len(header) + following.start() if following else len(text)
    return text[:start] + change(text[start:end]) + text[end:]


def api(method, path, body=None):
    request = urllib.request.Request(
        "https://api.github.com/repos/Kukutx/Viper/" + path,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "Viper-modernization"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def guard_release_steps(text):
    pattern = re.compile(r"^      - .*?(?=^      - |^  [A-Za-z0-9_-]+:|\Z)", re.M | re.S)
    def change(match):
        block = match[0]
        if "uses: softprops/action-gh-release@" not in block:
            return block
        condition = re.search(r"^        if: (.+)$", block, re.M)
        if condition:
            expression = condition[1].strip()
            if expression.startswith("${{") and expression.endswith("}}"):
                expression = expression[3:-2].strip()
            return block[:condition.start()] + "        if: ${{ inputs.upload-artifact && (" + expression + ") }}" + block[condition.end():]
        return re.sub(r"(^        uses: softprops/action-gh-release@[^\n]+\n)", r"\1        if: inputs.upload-artifact\n", block, count=1, flags=re.M)
    return pattern.sub(change, text)


def main():
    if os.environ.get("GITHUB_REPOSITORY") != "Kukutx/Viper" or os.environ.get("GITHUB_REF") != "refs/heads/codex/viper-foundation-modernization":
        raise ValueError("Candidate preparation is restricted to the requested task branch")
    head = viper.run("git", "rev-parse", "HEAD").strip()
    if head != os.environ["GITHUB_SHA"]:
        raise ValueError("Checkout does not match workflow revision")

    build = ROOT / ".github/workflows/flutter-build.yml"
    text = build.read_text()
    text = edit_job(text, "generate-sbom", lambda block: replace(block, "    permissions:\n      contents: write\n\n", ""))
    text = edit_job(text, "build-rustdesk-android-universal", lambda block: replace(block, "name: rustdesk-${{ env.VERSION }}-${{ matrix.job.arch }}.apk", "name: rustdesk-${{ env.VERSION }}-universal.apk"))
    def remove_inactive_web(block):
        if "    if: False\n" not in block:
            raise ValueError("Refusing to remove an enabled web job")
        return ""
    text = edit_job(text, "build-rustdesk-web", remove_inactive_web)
    text = guard_release_steps(text)
    build.write_text(text.rstrip() + "\n")

    (ROOT / ".github/workflows/playground.yml").unlink()
    helper = ROOT / ".github/workflows/third-party-RustDeskTempTopMostWindow.yml"
    helper.write_text(replace(helper.read_text(), "required: true", "required: false", count=4))
    for name in ("flutter-nightly.yml", "flutter-tag.yml", "fdroid.yml"):
        path = ROOT / ".github/workflows" / name
        text = path.read_text()
        text = replace(text, "\njobs:\n", "\npermissions:\n  contents: write\n\nconcurrency:\n  group: " + name[:-4] + "-${{ github.ref }}\n  cancel-in-progress: false\n\njobs:\n")
        if name == "fdroid.yml":
            text = replace(text, "api.github.com/repos/rustdesk/rustdesk/releases/latest", "api.github.com/repos/${GITHUB_REPOSITORY}/releases/latest")
        path.write_text(text.rstrip() + "\n")

    source = ROOT / "tools/viper.py"
    text = source.read_text()
    text = replace(text, 'path.name != "release-manifest.json"', 'path != directory / "release-manifest.json"', count=2)
    text = replace(text, 'sorted(directory.rglob("*"))', 'sorted(directory.rglob("*"), key=lambda p: p.relative_to(directory).as_posix())')
    source.write_text(text)
    tests = ROOT / "tools/tests/test_viper.py"
    test = '''    def test_nested_manifest_is_not_excluded(self):
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "release-manifest.json").write_text("tracked artifact")
        data = self.save()
        self.assertEqual(len(data["artifacts"]), 2)
        (nested / "release-manifest.json").write_text("tampered")
        with self.assertRaises(ValueError):
            viper.verify_manifest(self.root)

'''
    tests.write_text(replace(tests.read_text(), '    def test_roundtrip(self):\n', test + '    def test_roundtrip(self):\n'))

    viper.actions(write=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tools/tests", "-v"], check=True)
    subprocess.run(["actionlint", "-shellcheck=", "-pyflakes="], check=True)
    (ROOT / ".github/workflows/prepare-modernization.yml").unlink()
    Path(__file__).unlink()
    subprocess.run(["git", "add", "--", ".github/workflows", "tools/viper.py", "tools/tests/test_viper.py", "tools/prepare_modernization.py"], check=True)
    viper.check()
    subprocess.run(["git", "diff", "--cached", "--check"], check=True)
    paths = viper.run("git", "diff", "--name-only", "HEAD").splitlines()
    entries = []
    for path in paths:
        if not (path.startswith(".github/workflows/") or path in ("tools/viper.py", "tools/tests/test_viper.py", "tools/prepare_modernization.py")):
            raise ValueError("Unexpected candidate file: " + path)
        file = ROOT / path
        entry = {"path": path, "mode": "100644", "type": "blob", "sha": None}
        if file.exists():
            raw = file.read_bytes()
            blob = api("POST", "git/blobs", {"content": raw.decode("utf-8"), "encoding": "utf-8"})
            expected = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
            if blob["sha"] != expected:
                raise ValueError("Uploaded blob does not match validated content")
            entry["sha"] = blob["sha"]
        entries.append(entry)
    parent = api("GET", "git/commits/" + head)
    print("CANDIDATE_PARENT=" + head, flush=True)
    print("CANDIDATE_BASE_TREE=" + parent["tree"]["sha"], flush=True)
    print("CANDIDATE_TREE_ELEMENTS=" + json.dumps(entries, separators=(",", ":")), flush=True)
    print("Validated blobs only: no tree, commit, branch, release or deployment was written.", flush=True)


if __name__ == "__main__":
    main()
