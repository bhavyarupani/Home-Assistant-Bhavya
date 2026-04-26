#!/usr/bin/env python3
"""Fail if runtime, secret, or generated files are tracked by Git."""

from __future__ import annotations

import fnmatch
import subprocess
import sys

FORBIDDEN_PATTERNS = (
    ".DS_Store",
    ".HA_VERSION",
    ".ha_build_info",
    ".shopping_list.json",
    ".storage/*",
    ".cloud/*",
    ".core/*",
    ".idea/*",
    "Git Clones/*",
    "home-assistant_v2.db*",
    "home-assistant.log*",
    "secrets.yaml",
    "zigbee.db*",
    "ha_github",
    "ha_github.pub",
    "*.db-shm",
    "*.db-wal",
    "*.pyc",
    "*/__pycache__/*",
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return result.stdout.splitlines()


def is_forbidden(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in FORBIDDEN_PATTERNS)


def main() -> int:
    forbidden = sorted(path for path in tracked_files() if is_forbidden(path))
    if not forbidden:
        print("No forbidden files are tracked.")
        return 0

    print("Forbidden files are tracked:")
    for path in forbidden:
        print(f"  - {path}")
    print("\nRemove them from Git and keep them ignored.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
