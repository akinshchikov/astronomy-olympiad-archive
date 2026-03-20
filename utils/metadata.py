from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from .fs_utils import normalize_whitespace, safe_filename, slugify_ascii, transliterate_to_ascii

SOURCE_ROLE_RANK = {
    "official": 5,
    "archive": 4,
    "mirror": 3,
    "community": 2,
    "annotated": 1,
}

PRIORITY_FAMILIES = [
    "vsosh_astronomy",
    "struve",
    "owao",
    "serbia_astronomy",
    "russia_team_qual",
    "spbao",
    "mao",
    "iao",
    "ioaa",
]

TASK_TOKENS = ("task", "tasks", "problem", "problems", "question", "questions", "задани", "задач")
SOLUTION_TOKENS = (
    "solution",
    "solutions",
    "ans",
    "answer",
    "answers",
    "answersheet",
    "otvet",
    "otvety",
    "resh",
    "resheni",
    "решен",
    "ответ",
)
SOLUTION_SHORT_TOKEN_PATTERN = re.compile(r"(?<![a-z0-9])sol(?![a-z0-9])")
MARKING_TOKENS = ("marking", "scheme", "criteria", "criterion", "критер", "scheme")
ANALYSIS_TOKENS = ("review", "разбор", "comment", "annotat")
ANNOTATED_TOKENS = ("annotat", "коммент", "разбор")
SCAN_TOKENS = ("scan", "скан")
TEAM_TOKENS = ("team", "group", "команд")
OBSERVATIONAL_TOKENS = (
    "observation",
    "observational",
    "planetarium",
    "telescope",
    "sky map",
    "skymap",
    "prak",
    "prakt",
    "practical",
    "nabl",
    "night",
    "day_time_observation",
    "outdoor",
)
THEORETICAL_TOKENS = (
    "theory",
    "theoretical",
    "teor",
    "short",
    "long",
    "data_analysis",
    "data analysis",
    "dataanalysis",
)
QUALIFYING_TOKENS = ("otbor", "qual", "qualifying", "dist", "school", "mun", "prigl", "invite", "отбор")
REGIONAL_TOKENS = ("regional", "/reg/", "_reg_", "-reg-", "рэ", "регион")
FINAL_TOKENS = ("final", "/final/", "-final-", "зе", "заключ")


def decoded_url_path(url: str) -> str:
    parsed = urlparse(url)
    return unquote(parsed.path)


def decoded_filename(url: str) -> str:
    path = PurePosixPath(decoded_url_path(url))
    return path.name


def infer_year(raw_text: str) -> int | None:
    text = unquote(raw_text).lower()

    season_match = re.search(r"(20\d{2})[-_/](20\d{2})", text)
    if season_match:
        return int(season_match.group(2))

    season_short_match = re.search(r"(?<!\d)(\d{2})[-_/](\d{2})(?!\d)", text)
    if season_short_match:
        left = int(season_short_match.group(1))
        right = int(season_short_match.group(2))
        if left >= 20 and right >= 20:
            century = 2000 if right < 90 else 1900
            if right < left:
                right += 100
            return century + right

    year_match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text)
    if year_match:
        return int(year_match.group(1))

    return None


def infer_language(*texts: str) -> str:
    full_text = " ".join(texts)
    if re.search(r"[А-Яа-яЁё]", full_text):
        return "ru"
    if full_text:
        return "en"
    return "unknown"


def infer_document_type(*texts: str) -> tuple[str, list[str]]:
    text = normalize_whitespace(" ".join(texts).lower())
    contains_tasks = any(token in text for token in TASK_TOKENS)
    combined_marker = any(
        marker in text
        for marker in (
            "taskssol",
            "tasks and solutions",
            "problems and solutions",
            "задания и решения",
            "задачи и решения",
        )
    )
    contains_solutions = (
        any(token in text for token in SOLUTION_TOKENS)
        or bool(SOLUTION_SHORT_TOKEN_PATTERN.search(text))
        or combined_marker
    )
    contains_marking = any(token in text for token in MARKING_TOKENS)
    contains_analysis = any(token in text for token in ANALYSIS_TOKENS)

    extra_types: list[str] = []
    if contains_tasks:
        extra_types.append("tasks")
    if contains_solutions:
        extra_types.append("solutions")
    if contains_marking:
        extra_types.append("marking")
    if contains_analysis:
        extra_types.append("analysis")

    if contains_marking:
        return "marking", extra_types
    if contains_analysis:
        return "analysis", extra_types
    if contains_solutions and not combined_marker:
        return "solutions", extra_types
    if contains_tasks:
        return "tasks", extra_types
    return "info", extra_types


def infer_stage(olympiad_family: str, *texts: str) -> tuple[str, str | None]:
    text = normalize_whitespace(" ".join(texts).lower())
    round_detail = None

    if olympiad_family == "vsosh_astronomy":
        if any(token in text for token in REGIONAL_TOKENS):
            return "regional", round_detail
        if any(token in text for token in FINAL_TOKENS):
            if any(token in text for token in THEORETICAL_TOKENS):
                round_detail = "theoretical"
            elif any(token in text for token in OBSERVATIONAL_TOKENS):
                round_detail = "observational"
            elif "test" in text:
                round_detail = "test"
            return "final", round_detail
        if any(token in text for token in QUALIFYING_TOKENS):
            return "qualifying", round_detail
        return "unknown", round_detail

    if any(token in text for token in TEAM_TOKENS):
        return "team", "team"
    if any(token in text for token in OBSERVATIONAL_TOKENS):
        return "observational", "observational"
    if any(token in text for token in THEORETICAL_TOKENS):
        return "theoretical", "theoretical_or_data_analysis"
    if any(token in text for token in FINAL_TOKENS):
        return "final", round_detail
    if any(token in text for token in REGIONAL_TOKENS):
        return "regional", round_detail
    if any(token in text for token in QUALIFYING_TOKENS):
        return "qualifying", round_detail
    return "unknown", round_detail


def infer_extension(url: str, content_type: str | None = None) -> str:
    path = decoded_filename(url).lower()
    if "." in path:
        ext = path.rsplit(".", 1)[1]
        if ext in {"pdf", "doc", "docx", "zip", "html", "htm", "txt"}:
            return ext
    if content_type:
        lowered = content_type.lower()
        if "pdf" in lowered:
            return "pdf"
        if "html" in lowered:
            return "html"
        if "zip" in lowered:
            return "zip"
    return "bin"


def infer_variant_tag(source_role: str, title: str, url: str, extra_types: list[str]) -> str:
    text = f"{title} {url}".lower()
    pieces = [source_role or "variant"]
    if any(token in text for token in SCAN_TOKENS):
        pieces.append("scan")
    if any(token in text for token in ANNOTATED_TOKENS):
        pieces.append("annotated")
    if len(extra_types) > 1:
        pieces.append("combined")
    return slugify_ascii("_".join(pieces), fallback="variant")


def source_domain(url: str) -> str:
    return urlparse(url).netloc.lower()


def confidence_score(year: int | None, stage: str, document_type: str, title: str) -> float:
    score = 0.35
    if year is not None:
        score += 0.25
    if stage != "unknown":
        score += 0.2
    if document_type != "info":
        score += 0.15
    if title:
        score += 0.05
    return round(min(score, 0.99), 2)


def year_tag(year: int | None) -> str:
    return str(year) if year is not None else "unknown-year"


def slugify_kebab(text: str, fallback: str = "file") -> str:
    return slugify_ascii(text, fallback=fallback).replace("_", "-")


def path_slug(text: str, fallback: str = "item") -> str:
    return slugify_kebab(text, fallback=fallback)


def _normalized_ascii_text(*texts: str) -> str:
    return normalize_whitespace(transliterate_to_ascii(" ".join(filter(None, texts))).lower())


def _append_unique(tags: list[str], tag: str | None) -> None:
    if tag and tag not in tags:
        tags.append(tag)


def _extract_grade_tag(ascii_text: str) -> str | None:
    grade = r"(?:4|5|6|7|8|9|10|11)"
    range_patterns = (
        rf"\b({grade})\s*[-_/]\s*({grade})\s*(?:kl|klass|class|grade)\b",
        rf"\b(?:tasks?|task|solutions?|solution|answers?|answer|criteria|marking|analysis|spdata|sol|ans|otvet|otvety)?(?:[-_ ]+(?:astr|astro|struve))?[-_ ]*({grade})[-_ ]+({grade})(?=[-_ ]+(?:rayon|raion|mun|sch|prigl|dist|otbor|reg|regional|final|teor|theor|prak|prakt|practical|test|bltz|blitz|bltest|obs|observ|msk|sky|telescope|planetarium|[0-9]{{2}}\b))",
        rf"\b({grade})\s*[-_/]\s*({grade})\b(?=\s*(?:kl|klass|class|grade|rayon|raion|mun|sch|prigl|dist|otbor|reg|regional|final|teor|theor|prak|prakt|practical|test|bltz|blitz|bltest|obs|observ|msk))",
    )
    single_patterns = (
        rf"\b({grade})\s*(?:kl|klass|class|grade)\b",
        rf"[?&]class=({grade})\b",
        rf"\b(?:tasks?|task|solutions?|solution|answers?|answer|criteria|marking|analysis|spdata|sol|ans|otvet|otvety)?(?:[-_ ]+(?:astr|astro|struve))?[-_ ]*({grade})(?=[-_ ]+(?:rayon|raion|mun|sch|prigl|dist|otbor|reg|regional|final|teor|theor|prak|prakt|practical|test|bltz|blitz|bltest|obs|observ|msk|sky|telescope|planetarium|[0-9]{{2}}\b))",
    )

    for pattern in range_patterns:
        match = re.search(pattern, ascii_text)
        if match:
            left = match.group(1)
            right = match.group(2)
            if left == right:
                return f"grade-{left}"
            return f"grade-{left}-{right}"

    for pattern in single_patterns:
        match = re.search(pattern, ascii_text)
        if match:
            return f"grade-{match.group(1)}"

    return None


def _extract_group_tag(ascii_text: str) -> str | None:
    patterns = (
        ("struve", r"\bstruve\b"),
        ("junior", r"\bjunior\b"),
        ("senior", r"\bsenior\b"),
    )
    for label, pattern in patterns:
        if re.search(pattern, ascii_text):
            return label

    group_match = re.search(r"\b(?:group|gruppa|team)\s*([a-z])\b", ascii_text)
    if group_match:
        return f"group-{group_match.group(1)}"

    return None


def _extract_round_number_tag(ascii_text: str) -> str | None:
    day_match = re.search(r"\bday\s*([1-4])\b", ascii_text)
    if day_match:
        return f"day-{day_match.group(1)}"

    tour_match = re.search(r"\b(?:tour|tur|round)\s*([1-4])\b", ascii_text)
    if tour_match:
        return f"round-{tour_match.group(1)}"

    return None


def _extract_qualifier_tag(ascii_text: str) -> str | None:
    patterns = (
        ("school", r"\bsch\b|school|shkol"),
        ("invitational", r"\bprigl\b|invite|invitat|priglas"),
        ("distance", r"\bdist\b|distance|distants"),
        ("selection", r"\botbor\b|selection"),
        ("rayon", r"\brayon\b|\braion\b|raionn"),
        ("municipal", r"\bmun\b|municipal|munitsip"),
    )
    for label, pattern in patterns:
        if re.search(pattern, ascii_text):
            return label
    return None


def _extract_track_tag(ascii_text: str, round_detail: str | None) -> str | None:
    if re.search(r"\bbl(?:tz|itz|test)\b", ascii_text):
        return "blitz"
    if re.search(r"\btest\b", ascii_text):
        return "test"
    if re.search(r"\bplanetarium\b", ascii_text):
        return "planetarium"
    if re.search(r"\bsky[\s_-]*map\b|\bskymap\b", ascii_text):
        return "sky-map"
    if re.search(r"\btelescope\b", ascii_text):
        return "telescope"
    if re.search(r"\bdata[_ -]*analysis\b|\bdataanalysis\b|\bda[_ -]+problem\b|\bda[_ -]+solution\b", ascii_text):
        return "data-analysis"
    if re.search(r"\bteor\b|\btheor(?:y|etical)?\b", ascii_text):
        return "theory"
    if re.search(r"\bprak\b|\bprakt\b|\bpractical\b", ascii_text):
        return "practical"

    round_tag_map = {
        "theoretical": "theory",
        "theoretical_or_data_analysis": "theory",
        "observational": "observational",
        "test": "test",
        "team": "team",
    }
    return round_tag_map.get(round_detail or "")


def _extract_material_tags(ascii_text: str, document_type: str, extension: str) -> list[str]:
    tags: list[str] = []
    explicit_patterns = (
        ("reference-data", r"\bspdata\b|spravoch|reference[_ -]*data|ephemer"),
        ("outdoor", r"\boutdoor\b"),
        ("night", r"\bnight\b"),
        ("questions", r"\bquestions?\b"),
        ("exam", r"\bexam(?:ination)?\b"),
        ("summary-answersheet", r"\bsummary[-_ ]*answersheet\b"),
        ("answersheet", r"\banswersheet\b"),
        ("index-page", r"\bindex\b"),
        ("results", r"\bresults?\b"),
        ("regulations", r"\bregulations?\b|\bporyadok\b|\bpolozheni"),
    )
    for label, pattern in explicit_patterns:
        if re.search(pattern, ascii_text):
            _append_unique(tags, label)

    order_match = re.search(r"\b(?:pr|prikaz|order)[-_ ]*(?:minpros|donm|msk|mos|edu)?[-_ ]*(\d{2,5})\b", ascii_text)
    if order_match:
        _append_unique(tags, f"order-{order_match.group(1)}")

    if extension in {"html", "htm"}:
        if document_type == "tasks":
            _append_unique(tags, "tasks-page")
        elif document_type == "solutions":
            _append_unique(tags, "solutions-page")
        else:
            _append_unique(tags, "info-page")

    if document_type == "tasks" and re.search(r"\bproblem[_ -]*sheet\b", ascii_text):
        _append_unique(tags, "problem-sheet")
    if document_type == "solutions" and re.search(r"\bsolution[_ -]*sheet\b", ascii_text):
        _append_unique(tags, "solution-sheet")
    return tags


def _fallback_detail_tag(
    *,
    olympiad_family: str,
    filename_original: str,
    source_title: str,
    source_role: str,
    stage_or_round: str,
    document_type: str,
    language: str,
) -> str:
    candidate_text = filename_original
    if not re.search(r"[A-Za-zА-Яа-яЁё]", candidate_text):
        candidate_text = source_title

    if "." in candidate_text:
        candidate_text = candidate_text.rsplit(".", 1)[0]

    slug = slugify_ascii(candidate_text, fallback="")
    if not slug:
        return "main"

    generic_tokens = {
        "annotated",
        "answer",
        "answers",
        "archive",
        "astr",
        "astronomy",
        "astro",
        "community",
        "criteria",
        "doc",
        "docx",
        "en",
        "final",
        "htm",
        "html",
        "iao",
        "info",
        "ioaa",
        "lang",
        "mao",
        "marking",
        "mirror",
        "observation",
        "observational",
        "official",
        "olympiad",
        "page",
        "pdf",
        "problem",
        "problems",
        "qualifying",
        "regional",
        "ru",
        "scan",
        "solution",
        "solutions",
        "spbao",
        "task",
        "tasks",
        "theoretical",
        "theory",
        "unknown",
        "vsosh",
        olympiad_family,
        stage_or_round,
        document_type,
        language,
        source_role,
    }
    cleaned_tokens = []
    for token in slug.split("_"):
        if not token or token in generic_tokens:
            continue
        if re.fullmatch(r"(?:19|20)\d{2}", token):
            continue
        if token.isdigit():
            continue
        cleaned_tokens.append(token)

    if not cleaned_tokens:
        return "main"

    return slugify_kebab("-".join(cleaned_tokens[:4]), fallback="main")


def infer_detail_tag(
    *,
    olympiad_family: str,
    stage_or_round: str,
    document_type: str,
    language: str,
    round_detail: str | None,
    extension: str,
    filename_original: str,
    source_title: str,
    source_url: str,
    parent_page_title: str = "",
    parent_page_url: str = "",
    source_role: str = "",
) -> str:
    ascii_text = _normalized_ascii_text(
        filename_original,
        source_title,
        source_url,
        parent_page_title,
        parent_page_url,
    )
    tags: list[str] = []
    _append_unique(tags, _extract_grade_tag(ascii_text))
    group_tag = _extract_group_tag(ascii_text)
    if not (olympiad_family == "struve" and group_tag == "struve"):
        _append_unique(tags, group_tag)
    _append_unique(tags, _extract_qualifier_tag(ascii_text))
    _append_unique(tags, _extract_round_number_tag(ascii_text))
    _append_unique(tags, _extract_track_tag(ascii_text, round_detail))
    for material_tag in _extract_material_tags(ascii_text, document_type, extension):
        _append_unique(tags, material_tag)

    if not tags:
        tags.append(
            _fallback_detail_tag(
                olympiad_family=olympiad_family,
                filename_original=filename_original,
                source_title=source_title,
                source_role=source_role,
                stage_or_round=stage_or_round,
                document_type=document_type,
                language=language,
            )
        )

    normalized_parts = [slugify_kebab(tag, fallback="main") for tag in tags if tag]
    normalized_parts = [part for part in normalized_parts if part]
    detail = "--".join(normalized_parts[:4])
    return detail[:96].rstrip("-") or "main"


def normalize_filename(
    *,
    year: int | None,
    olympiad_family: str,
    stage_or_round: str,
    document_type: str,
    language: str,
    detail_tag: str,
    variant_tag: str,
    extension: str,
) -> str:
    year_part = year_tag(year)
    ext = extension.lower()
    if ext == "htm":
        ext = "html"
    detail_parts = [part for part in detail_tag.split("--") if part]
    parts = [
        year_part,
        slugify_kebab(olympiad_family, fallback="olympiad"),
        slugify_kebab(stage_or_round, fallback="stage"),
        slugify_kebab(document_type, fallback="document"),
        slugify_kebab(language, fallback="lang"),
    ]
    parts.extend(detail_parts or ["main"])
    parts.append(slugify_kebab(variant_tag, fallback="variant"))
    safe_parts = [safe_filename(part, fallback="unknown") for part in parts]
    return "--".join(safe_parts) + f".{ext}"
