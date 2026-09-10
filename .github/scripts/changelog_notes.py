#!/usr/bin/env python3
"""Check CHANGELOG.md against the release version and emit the release body.

There are two jobs here:

  * Check that the version in the CHANGELOG matches the release.

  * Copy the Executive Summary to the Github release body.

Usage:
    changelog_notes.py --version X.Y.Z [--output description.txt]

Without --output the body goes to stdout, so `--output /dev/null` is a
validation-only run.
"""
import argparse
import re
import sys
from pathlib import Path

CHANGELOG = Path("CHANGELOG.md")

# "v1.0.1 --- unreleased", "v1.0.1 --- October 3, 2026"
HEADER_RE = re.compile(r"^v(?P<version>\S+)\s+---\s+(?P<date>.+?)\s*$")

SUMMARY_RE = re.compile(r"^#\s+\S*\s*Executive Summary\b", re.IGNORECASE)
TOP_HEADING_RE = re.compile(r"^#\s+")

# github.com/HDFGroup/hsds/blob/master/... in the summary -> .../blob/<tag>/...
BLOB_MASTER = "/HDFGroup/hsds/blob/master/"


def fail(msg):
    print(f"::error::{msg}", file=sys.stderr)
    raise SystemExit(1)


def read_lines():
    if not CHANGELOG.is_file():
        fail(f"{CHANGELOG} not found - the release body is generated from it")
    return CHANGELOG.read_text(encoding="utf-8").splitlines()


def check_version(lines, version):
    """Fail unless CHANGELOG.md's first line names the version being released."""
    for line in lines:
        if not line.strip():
            continue
        match = HEADER_RE.match(line)
        if not match:
            fail(
                f"{CHANGELOG} must start with a line like "
                f"'v{version} --- <date>', got {line!r}"
            )
        if match.group("version") != version:
            fail(
                f"{CHANGELOG} describes v{match.group('version')} but the "
                f"release is {version}. Update the changelog's first line "
                "along with the version in pyproject.toml."
            )
        if match.group("date").strip().lower() == "unreleased":
            fail(
                f"{CHANGELOG} still says 'unreleased'. Put the release date on "
                "the first line."
            )
        return
    fail(f"{CHANGELOG} is empty")


def extract_summary(lines):
    """The Executive Summary section, without the headings that follow it."""
    body = []
    for line in lines:
        if body:
            if TOP_HEADING_RE.match(line):
                break
            body.append(line)
        elif SUMMARY_RE.match(line):
            body.append(line)

    if not body:
        fail(
            f"{CHANGELOG} has no 'Executive Summary' top-level heading."
        )

    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body) + "\n"


def pin_links(summary, tag):
    return summary.replace(BLOB_MASTER, f"/HDFGroup/hsds/blob/{tag}/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="version being released")
    parser.add_argument("--output", help="write the release body here (default: stdout)")
    args = parser.parse_args()

    lines = read_lines()
    check_version(lines, args.version)
    summary = pin_links(extract_summary(lines), f"v{args.version}")

    if args.output:
        Path(args.output).write_text(summary, encoding="utf-8")
        print(f"wrote {len(summary.splitlines())} lines to {args.output}")
    else:
        sys.stdout.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
