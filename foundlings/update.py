#!/usr/bin/env python3
"""Keep the local kache fork current and installed.

    update.py merge [REF]   merge REF (default: newest stable upstream tag) into `foundlings`
    update.py build         release build plus the fork's own key tests
    update.py install       install the built pair over ~/.cargo/bin and restart the daemon
    update.py status        branch, upstream distance, installed version

The fork lives on branch `foundlings`; upstream is the `upstream` remote. Upstream
releases are merged in (never rebased) so the fork's commits keep their ids.
`install` refuses while a cargo build is running: a new kache binary on PATH would
be picked up mid-build against the old daemon.
"""

import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

FORK = Path(__file__).resolve().parents[1]
BRANCH = "foundlings"
STABLE_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
KEY_TESTS = (
    "clippy_manifest",
    "only_the_bare_relative",
    "clippy_identity",
    "a_rerun_over_leftovers",
    "the_switch_does_not_clear",
    "clearing_out_dir_leftovers",
)


def run(*command: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, cwd=FORK, check=check, text=True, capture_output=capture)


def newest_stable_tag() -> str:
    tags = run("git", "tag", "--sort=-v:refname", capture=True).stdout.split()
    return next(tag for tag in tags if STABLE_TAG.match(tag))


def merge(ref: str | None) -> int:
    run("git", "fetch", "upstream", "--tags")
    run("git", "switch", BRANCH)
    target = ref or newest_stable_tag()
    done = run("git", "merge", "--no-edit", target, check=False)
    if done.returncode != 0:
        print(f"update: merging {target} conflicts; resolve, commit, then run build", file=sys.stderr)
        return 1
    print(f"update: merged {target} into {BRANCH}")
    return 0


def build() -> int:
    run("cargo", "build", "--locked", "--release")
    run("cargo", "test", "--locked", "--lib", "--", *KEY_TESTS)
    return 0


def builds_running() -> list[str]:
    found = run("pgrep", "-l", "^(cargo|rustc|clippy-driver)$", check=False, capture=True).stdout
    return [line for line in found.splitlines() if line.strip()]


def install() -> int:
    busy = builds_running()
    if busy:
        print("update: builds are running; install between builds:\n  " + "\n  ".join(busy), file=sys.stderr)
        return 1
    run("kache", "daemon", "stop", check=False)
    run("cargo", "install", "--locked", "--path", ".", "--target-dir", "target", "--force")
    kache = shutil.which("kache")
    print(f"update: kache on PATH is {kache}")
    run("kache", "daemon", "install")
    run("kache", "daemon", "restart")
    run("kache", "--version")
    run("kache", "doctor")
    return 0


def status() -> int:
    run("git", "status", "-sb")
    run("git", "log", "--oneline", f"{newest_stable_tag()}..{BRANCH}")
    run("kache", "--version", check=False)
    return 0


def main(arguments: Sequence[str]) -> int:
    if not arguments or arguments[0] not in {"merge", "build", "install", "status"}:
        print(__doc__, file=sys.stderr)
        return 2
    command, rest = arguments[0], arguments[1:]
    if command == "merge":
        return merge(rest[0] if rest else None)
    return {"build": build, "install": install, "status": status}[command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
