#!/usr/bin/env python3
"""Dump the live FastAPI schema to the committed spec files.

Usage:
    python scripts/export_openapi.py            # write openapi/openapi.json (+ versioned copy)
    python scripts/export_openapi.py --check    # exit 1 if the committed spec is stale

The versioned file (``openapi-v<major.minor.patch>.json``) is the semantic
contract; ``openapi.json`` is a stable path that always points at the current
version.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.main import app

SPEC_DIR = Path(__file__).resolve().parent.parent / "openapi"


def render() -> tuple[str, str]:
    spec = app.openapi()
    assert spec["openapi"].startswith("3.1"), spec["openapi"]
    version = spec["info"]["version"]
    text = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    return version, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify committed spec is current")
    args = parser.parse_args()

    version, text = render()
    stable = SPEC_DIR / "openapi.json"
    versioned = SPEC_DIR / f"openapi-v{version}.json"

    if args.check:
        stale = [
            p.name
            for p in (stable, versioned)
            if not p.exists() or p.read_text() != text
        ]
        if stale:
            print(f"stale/missing spec files: {', '.join(stale)}", file=sys.stderr)
            print("run: python scripts/export_openapi.py", file=sys.stderr)
            return 1
        print(f"OpenAPI spec is current (v{version})")
        return 0

    SPEC_DIR.mkdir(exist_ok=True)
    stable.write_text(text)
    versioned.write_text(text)
    print(f"wrote {stable} and {versioned} (v{version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
