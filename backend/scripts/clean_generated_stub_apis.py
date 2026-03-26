#!/usr/bin/env python3
"""Remove strict query/path typing from generated FastAPI stub API signatures.

OpenAPI Generator emits `Field(..., strict=True, ...)` in endpoint parameter annotations.
For URL query/path values, FastAPI receives strings and strict int parsing causes 422.
This script strips `strict=True` from generated API files after each regeneration.

Workaround note:
This is a temporary workaround for a known generator-template issue in the
`python-fastapi` stubs, where strict typing is applied to URL parameters.
URL parameters are string-encoded over HTTP, so strict integer validation
rejects valid requests like `?limit=25` before endpoint logic runs.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APIS_DIR = ROOT / "src" / "generated" / "server_stubs" / "apis"


def remove_strict_flags(text: str) -> str:
    # Remove strict=True regardless of its position in Field(...).
    text = re.sub(r"\bstrict=True\s*,\s*", "", text)
    text = re.sub(r",\s*strict=True\b", "", text)
    return text


def main() -> int:
    if not APIS_DIR.exists():
        print(f"No generated APIs found at {APIS_DIR}")
        return 0

    changed_files = 0
    replacements = 0

    for file_path in sorted(APIS_DIR.glob("*_api*.py")):
        original = file_path.read_text(encoding="utf-8")
        updated = remove_strict_flags(original)
        if updated != original:
            replacements += original.count("strict=True")
            file_path.write_text(updated, encoding="utf-8")
            changed_files += 1

    print(
        f"Sanitized generated stubs: changed {changed_files} file(s), "
        f"removed {replacements} strict flag occurrence(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

