import csv
import json
import re
from pathlib import Path
from unittest import TestCase

import build_indices
from utils.source_configs import SOURCE_DEFINITIONS


ROOT = Path(__file__).resolve().parents[1]


def csv_rows(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def jsonl_count(relative: str) -> int:
    with (ROOT / relative).open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


class SourceCoverageCatalogTests(TestCase):
    def test_catalog_covers_all_configured_and_retained_candidate_sources(self):
        rows = csv_rows("data/audits/source_coverage.csv")
        by_source = {row["source_id"]: row for row in rows}
        self.assertEqual(len(rows), len(by_source))

        configured = {source.source_id for source in SOURCE_DEFINITIONS}
        self.assertEqual(
            configured,
            {row["source_id"] for row in rows if row["configured"] == "true"},
        )
        self.assertEqual(
            {
                "apao_issp_official",
                "bangladesh_bdoaa_official",
                "indonesia_osn_official",
                "israel_multispace_archive",
                "korea_kao_official",
                "romania_astronomy_official",
                "taiwan_astronomy_deferred_reference",
                "ukraine_usao_official",
            },
            {
                row["source_id"]
                for row in rows
                if row["content_state"] in {"unresolved", "deferred"}
            },
        )

    def test_catalog_dimensions_use_allowed_values(self):
        rows = csv_rows("data/audits/source_coverage.csv")
        allowed = {
            "configured": {"true", "false"},
            "content_state": {"indexed", "metadata_only", "unresolved", "deferred"},
            "completeness": {"known_complete_scope", "partial_archive", "sample_only", "unknown"},
            "access_state": {
                "open",
                "partially_accessible",
                "robots_blocked",
                "policy_blocked",
                "form_gated",
                "dead_links",
                "no_archive_found",
                "not_applicable",
            },
            "source_role": {"official", "mirror", "archive"},
            "redistribution_status": {"unknown", "explicit-no-redistribution"},
        }
        for field, values in allowed.items():
            with self.subTest(field=field):
                self.assertLessEqual({row[field] for row in rows}, values)

    def test_family_coverage_view_contains_every_catalog_and_public_index_family(self):
        files = csv_rows("data/indices/files_index.csv")
        olympiads = csv_rows("data/indices/olympiads_index.csv")
        rows = build_indices.family_coverage_rows(ROOT, files, olympiads, None)
        family_ids = {str(row["family_id"]) for row in rows}
        catalog_families = {row["family"] for row in csv_rows("data/audits/source_coverage.csv")}
        index_families = {row["olympiad_family"] for row in olympiads}
        self.assertEqual(family_ids, catalog_families)
        self.assertLessEqual(index_families, family_ids)
        self.assertTrue(all(row["name_en"] and row["name_ru"] for row in rows))

    def test_public_docs_use_neutral_coverage_language_and_current_counts(self):
        docs = {
            relative: (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "README.md",
                "README.ru.md",
                "PUBLISHING.md",
                "AGENTS.md",
                "docs/releases/v0.6.0.md",
                "docs/releases/v0.6.1.md",
            )
        }
        wave = "bat" + "ch"
        prohibited = re.compile(
            rf"{wave}\s+[abc]|{wave}_c|global_expansion_{wave}_c|"
            r"core base" r"line|base" r"line families|"
            r"newly ingested fam" r"ilies|second[- ]cl" r"ass",
            re.IGNORECASE,
        )
        for relative, text in docs.items():
            with self.subTest(relative=relative):
                self.assertIsNone(prohibited.search(text))

        counts = {
            len(csv_rows("data/manifests/source_candidates.csv")),
            jsonl_count("data/manifests/discovered_documents.jsonl"),
            len(csv_rows("data/indices/files_index.csv")),
            len(csv_rows("data/indices/olympiads_index.csv")),
            len(csv_rows("data/indices/relation_groups.csv")),
            len({row["olympiad_family"] for row in csv_rows("data/indices/files_index.csv")}),
            len({row["olympiad_family"] for row in csv_rows("data/indices/olympiads_index.csv")}),
        }
        for relative in ("README.md", "README.ru.md", "docs/releases/v0.6.1.md"):
            compact = re.sub(r"[,\s]", "", docs[relative])
            with self.subTest(relative=relative):
                self.assertTrue(all(str(count) in compact for count in counts))

        self.assertLessEqual(
            set(json.loads((ROOT / "data/config/family_history.json").read_text(encoding="utf-8"))),
            {row["family_id"] for row in csv_rows("data/config/family_metadata.csv")},
        )
