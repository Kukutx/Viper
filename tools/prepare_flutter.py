"""Validate the shared SDK, bridge and locked dependencies before packaging."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def prepare(root: Path = ROOT) -> None:
    for tool, arguments in (("flutter_sdk.py", []), ("bridge.py", ["check"]),
                            ("check_bridge_outputs.py", [])):
        subprocess.run([sys.executable, str(root / "tools" / tool), *arguments],
                       cwd=root, check=True)
    flutter = shutil.which("flutter")
    if flutter is None:
        raise RuntimeError("Pinned Flutter SDK is missing")
    subprocess.run([flutter, "pub", "get", "--enforce-lockfile"],
                   cwd=root / "flutter", check=True)
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--",
                    "flutter/pubspec.yaml", "flutter/pubspec.lock", "Cargo.lock"],
                   cwd=root, check=True)


def main() -> int:
    try:
        prepare()
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
