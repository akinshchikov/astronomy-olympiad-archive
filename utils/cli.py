from __future__ import annotations

import argparse
from pathlib import Path


def build_common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root directory.",
    )
    parser.add_argument(
        "--families",
        nargs="*",
        default=None,
        help="Restrict processing to selected olympiad families.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Resolve actions without downloading data.")
    parser.add_argument("--limit", type=int, default=None, help="Optional item limit for faster test runs.")
    return parser

