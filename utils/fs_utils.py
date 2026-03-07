from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable

CYRILLIC_TO_ASCII = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def transliterate_to_ascii(text: str) -> str:
    chars: list[str] = []
    for char in text:
        lower = char.lower()
        if lower in CYRILLIC_TO_ASCII:
            ascii_char = CYRILLIC_TO_ASCII[lower]
            chars.append(ascii_char.upper() if char.isupper() else ascii_char)
            continue
        chars.append(char)
    normalized = unicodedata.normalize("NFKD", "".join(chars))
    return normalized.encode("ascii", "ignore").decode("ascii")


def slugify_ascii(text: str, fallback: str = "file") -> str:
    ascii_text = transliterate_to_ascii(text)
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "_", ascii_text)
    ascii_text = re.sub(r"_+", "_", ascii_text).strip("_")
    return ascii_text or fallback


def safe_filename(text: str, fallback: str = "file") -> str:
    ascii_text = transliterate_to_ascii(text)
    ascii_text = re.sub(r"[^\w.\-]+", "_", ascii_text, flags=re.ASCII)
    ascii_text = re.sub(r"_+", "_", ascii_text).strip("._")
    return ascii_text or fallback


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

