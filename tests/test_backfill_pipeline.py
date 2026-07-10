from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import build_indices
import crawl_source
import discover_sources
import import_manual_files
import normalize_archive
from utils.fs_utils import load_jsonl, write_jsonl
from utils.metadata import decoded_filename, infer_document_type, infer_extension
from utils.models import SourceDefinition


def fake_http_client(responses: dict[str, SimpleNamespace]):
    class FakeHttpClient:
        def __init__(self, logger=None, dry_run: bool = False):
            self.logger = logger
            self.dry_run = dry_run

        def fetch(self, url: str) -> SimpleNamespace:
            if url not in responses:
                raise AssertionError(f"Unexpected URL: {url}")
            return responses[url]

    return FakeHttpClient


def fake_response(url: str, html: str, status_code: int = 200) -> SimpleNamespace:
    return SimpleNamespace(
        final_url=url,
        status_code=status_code,
        text=html,
        content=html.encode("utf-8"),
        headers={"Content-Type": "text/html; charset=utf-8"},
    )


def make_download_row(root: Path, *, name: str, raw_suffix: str, raw_text: str, txt_text: str = "", **overrides) -> dict:
    raw_path = root / "data" / "raw" / f"{name}{raw_suffix}"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(raw_text, encoding="utf-8")

    txt_path = raw_path.with_suffix(".txt")
    txt_path_value = ""
    if txt_text:
        txt_path.write_text(txt_text, encoding="utf-8")
        txt_path_value = str(txt_path)

    row = {
        "candidate_id": name,
        "source_id": "iao_eaae_index",
        "olympiad_family": "iao",
        "year": None,
        "stage_or_round": "unknown",
        "language": "en",
        "document_type": "tasks",
        "source_url": f"https://example.org/{name}",
        "source_domain": "example.org",
        "source_title": "",
        "source_priority": 1,
        "source_role": "archive",
        "parent_page_url": "",
        "parent_page_title": "",
        "filename_original": name,
        "extension": raw_suffix.lstrip("."),
        "variant_tag": "archive",
        "round_detail": None,
        "notes": "",
        "seed_context": {},
        "raw_path": str(raw_path),
        "txt_path": txt_path_value,
        "status": "downloaded",
        "content_type": "text/html; charset=utf-8" if raw_suffix in {".html", ".htm"} or txt_text else "",
    }
    row.update(overrides)
    return row


class BackfillPipelineTests(TestCase):
    def test_owao_discovery_keeps_round_context_and_access_notes(self) -> None:
        urls = [f"https://owao.siriusolymp.ru/{year}en/tasks" for year in (2025, 2024, 2023, 2022)]
        pages = {
            urls[0]: """<title>OWAO 2025</title><h2>Theoretical Round</h2>
                <a href='https://my.sirius.online/content/theory-problems.pdf'>Problems</a>
                <a href='https://my.sirius.online/content/theory-solutions.pdf'>Solutions</a>
                <h2>Practical Round</h2><a href='https://my.sirius.online/content/practical-problems.pdf'>Problems</a>
                <a href='https://my.sirius.online/content/practical-solutions.pdf'>Solutions</a>""",
            urls[1]: """<title>OWAO 2024</title><h2>Practical Round</h2>
                <a href='https://nextcloud-storage.talantiuspeh.ru/task-files'>Files to the tasks</a>
                <a href='https://nextcloud-storage.talantiuspeh.ru/problems'>Problems</a>
                <a href='https://nextcloud-storage.talantiuspeh.ru/solutions'>Solutions</a>
                <h2>Observation Round</h2><a href='https://uts.astroedu.ru/quiz'>Problems and Solutions</a>""",
            urls[2]: """<title>OWAO 2023</title><h2>Theoretical Round</h2>
                <a href='https://disk.yandex.ru/problems'>Problems</a><a href='https://disk.yandex.ru/solutions'>Solutions</a>
                <h2>Express Round and Observation Round</h2><a href='https://edu.sirius.online/item'>Problems and Solutions</a>""",
            urls[3]: """<title>OWAO 2022</title><h2>Theoretical Round</h2><a href='https://disk.yandex.ru/theory'>Problems</a>
                <h2>Practical Round</h2><a href='https://disk.yandex.ru/files'>Files to the tasks</a><a href='https://disk.yandex.ru/practice'>Solutions</a>""",
        }
        source = SourceDefinition("owao_tasks_official", "OWAO", "owao", "official", 1, "static", urls,
            extras={"default_context": {"record_seed_page": False, "follow_second_hop": False}})
        with TemporaryDirectory() as tmpdir, patch.object(discover_sources, "SOURCE_DEFINITIONS", [source]), patch.object(
            discover_sources, "HttpClient", fake_http_client({url: fake_response(url, html) for url, html in pages.items()})
        ):
            root = Path(tmpdir)
            self.assertEqual(discover_sources.discover_documents(root, None, False, None), 0)
            rows = load_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl")
        by_url = {row["source_url"]: row for row in rows}
        self.assertEqual(by_url["https://my.sirius.online/content/practical-problems.pdf"]["stage_or_round"], "practical")
        self.assertEqual(by_url["https://nextcloud-storage.talantiuspeh.ru/task-files"]["document_type"], "reference_data")
        combined = by_url["https://uts.astroedu.ru/quiz"]
        self.assertEqual(combined["document_type"], "solutions")
        self.assertIn("extra_types=tasks,solutions", combined["notes"])
        self.assertIn("discovery_only", combined["notes"])
        self.assertEqual(by_url["https://edu.sirius.online/item"]["round_detail"], "express_and_observational")
        self.assertEqual({row["year"] for row in rows}, {2022, 2023, 2024, 2025})
        parsed = discover_sources.owao_page_links(
            "<h2>2025</h2><h3>Theoretical Round</h3><a href='a.pdf'>Problems</a>"
            "<h2>2022</h2><h3>Practical Round</h3><a href='b.pdf'>Problems</a>",
            "https://owao.siriusolymp.ru/2025en/tasks",
        )
        self.assertEqual([(link["year"], link["section"]) for link in parsed], [(2025, "Theoretical Round"), (2022, "Practical Round")])
        nested = discover_sources.owao_page_links(
            "<div field='text'>2024</div><div field='tn_text_1'>Practical Round</div>"
            "<div field='tn_text_2'><a href='files'>Files to the tasks</a></div>",
            "https://owao.siriusolymp.ru/2025en/tasks",
        )
        self.assertEqual(nested[0]["text"], "Files to the tasks")
        self.assertEqual(nested[0]["year"], 2024)

    def test_manual_owao_import_feeds_normalization(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manual_root = root / "data" / "manual" / "owao"
            manual_root.mkdir(parents=True)
            pdf_path = manual_root / "2025-theory.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n%manual\n")
            write_jsonl(manual_root / "manual_manifest.jsonl", [{
                "source_url": "https://my.sirius.online/content/2025-theory.pdf", "olympiad_family": "owao",
                "year": 2025, "stage_or_round": "theoretical", "round_detail": "theoretical",
                "document_type": "tasks", "language": "en", "variant_tag": "official",
                "filename_original": "2025-theory.pdf", "local_path": "2025-theory.pdf",
            }])
            self.assertEqual(import_manual_files.import_manual_files(root), 1)
            downloaded = load_jsonl(root / "data" / "manifests" / "download_manifest.jsonl")
            self.assertEqual(downloaded[0]["status"], "manual")
            self.assertEqual(normalize_archive.normalize(root, None, False, None), 0)
            normalized = load_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl")
            self.assertEqual(normalized[0]["stage_or_round"], "theoretical")
    def test_metadata_handles_drupal_query_file_urls(self) -> None:
        url = "http://school.astro.spbu.ru/?q=system/files/10%20%D0%BA%D0%BB%D0%B0%D1%81%D1%81%20-%20%D1%80%D0%B5%D1%88%D0%B5%D0%BD%D0%B8%D1%8F_51.pdf"
        self.assertEqual(decoded_filename(url), "10 класс - решения_51.pdf")
        self.assertEqual(infer_extension(url), "pdf")

    def test_vsosh_astroedu_2026_final_filename_metadata(self) -> None:
        seed = {
            "source_id": "vsosh_astroedu_archive",
            "olympiad_family": "vsosh_astronomy",
            "source_role": "archive",
            "source_priority": 1,
        }
        expected = {
            "vos-2026-final-prob-T-9.pdf": ("tasks", "theoretical"),
            "vos-2026-final-sol-T-9.pdf": ("solutions", "theoretical"),
            "vos-2026-final-prob-P-10.pdf": ("tasks", "practical"),
            "vos-2026-final-sol-P-10.pdf": ("solutions", "practical"),
            "vos-2026-final-prob-B-11.pdf": ("tasks", "test"),
            "vos-2026-final-sol-B-11.pdf": ("solutions", "test"),
        }

        for filename, (document_type, round_detail) in expected.items():
            with self.subTest(filename=filename):
                entry = discover_sources.build_candidate_entry(
                    seed,
                    href=f"https://astroedu.ru/assets/problems/vos/2026/{filename}",
                    link_text=filename,
                    page_title="Задания",
                    parent_page_url="https://astroedu.ru/vos/problems",
                    parent_page_title="Задания",
                    context={},
                )
                self.assertEqual(entry["year"], 2026)
                self.assertEqual(entry["stage_or_round"], "final")
                self.assertEqual(entry["document_type"], document_type)
                self.assertEqual(entry["round_detail"], round_detail)

    def test_vsosh_reference_data_is_not_classified_as_tasks(self) -> None:
        for title, url in (
            (
                "9-11 кл. справочные данные",
                "https://vos.olimpiada.ru/files/spdata-astr-9-11-reg-25-26.pdf",
            ),
            (
                "2026",
                "https://astroedu.ru/assets/problems/vos/vos-spdata-2026.pdf",
            ),
        ):
            with self.subTest(url=url):
                document_type, extra_types = infer_document_type(title, url, "Задания")
                self.assertEqual(document_type, "reference_data")
                self.assertEqual(extra_types, ["reference_data"])

    def test_vsosh_2026_coverage_reports_partial_final_materials(self) -> None:
        discovered = []
        for day in (1, 2):
            for grade in (9, 10, 11):
                for short_type, document_type in (("prob", "tasks"), ("sol", "solutions")):
                    filename = f"vos-2026-reg-{short_type}-day{day}-{grade}.pdf"
                    discovered.append(
                        {
                            "candidate_id": filename,
                            "source_id": "vsosh_astroedu_archive",
                            "olympiad_family": "vsosh_astronomy",
                            "year": 2026,
                            "stage_or_round": "regional",
                            "round_detail": None,
                            "document_type": document_type,
                            "filename_original": filename,
                            "source_title": str(grade),
                            "source_url": f"https://example.test/{filename}",
                        }
                    )

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl", discovered)
            write_jsonl(root / "data" / "manifests" / "download_manifest.jsonl", [])
            write_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl", [])

            result = build_indices.build(root, families={"vsosh_astronomy"})

            self.assertEqual(result, 0)
            report = (root / "data" / "indices" / "coverage_report.md").read_text(encoding="utf-8")
            self.assertIn("| Regional day 1 | tasks: 9,10,11; solutions: 9,10,11 | complete |", report)
            self.assertIn("| Final theoretical | tasks: none; solutions: none | missing |", report)
            self.assertIn("- Core tasks/solutions: partial (2/5 components complete).", report)

    def test_discovery_uses_seed_context_and_skips_container_seed_page(self) -> None:
        seed_url = "https://example.org/archive"
        pdf_url = "https://example.org/files/final-2024.pdf"
        responses = {
            seed_url: fake_response(
                seed_url,
                """
                <html>
                  <title>Example archive</title>
                  <a href="/files/final-2024.pdf">Final tasks PDF</a>
                </html>
                """,
            )
        }
        source = SourceDefinition(
            source_id="example_archive",
            label="Example archive",
            olympiad_family="iao",
            source_role="archive",
            source_priority=1,
            strategy="static",
            seed_urls=[seed_url],
            extras={"default_context": {"record_seed_page": False, "year": 2024, "stage_or_round": "final"}},
        )

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with patch.object(discover_sources, "SOURCE_DEFINITIONS", [source]), patch.object(
                discover_sources,
                "HttpClient",
                fake_http_client(responses),
            ):
                result = discover_sources.discover_documents(root, families=None, dry_run=False, limit=None)

            self.assertEqual(result, 0)
            discovered = load_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl")
            self.assertEqual(len(discovered), 1)
            self.assertEqual(discovered[0]["source_url"], pdf_url)
            self.assertEqual(discovered[0]["year"], 2024)
            self.assertEqual(discovered[0]["stage_or_round"], "final")

    def test_discovery_follows_iao_second_hop_from_language_selector(self) -> None:
        seed_url = "https://example.org/iao"
        selector_url = "https://example.org/2000/vi00us_z.html"
        english_url = "https://example.org/2000/vi00us_e.html"
        doc_url = "https://example.org/2000/vi00us_e.doc"
        responses = {
            seed_url: fake_response(
                seed_url,
                f"""
                <html>
                  <title>IAO archive</title>
                  <a href="{selector_url}">2000 problems</a>
                </html>
                """,
            ),
            selector_url: fake_response(
                selector_url,
                """
                <html>
                  <title>VI IAO 2000 problems</title>
                  <p>Languages: English, Russian. Solutions not ready.</p>
                  <a href="vi00us_e.html">English</a>
                </html>
                """,
            ),
            english_url: fake_response(
                english_url,
                """
                <html>
                  <title>VI IAO 2000 problems</title>
                  <a href="vi00us_e.doc">Problems DOC</a>
                </html>
                """,
            ),
        }
        source = SourceDefinition(
            source_id="iao_eaae_index",
            label="IAO index",
            olympiad_family="iao",
            source_role="archive",
            source_priority=1,
            strategy="static",
            seed_urls=[seed_url],
            extras={"default_context": {"record_seed_page": False, "follow_second_hop": True, "max_follow_depth": 2}},
        )

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with patch.object(discover_sources, "SOURCE_DEFINITIONS", [source]), patch.object(
                discover_sources,
                "HttpClient",
                fake_http_client(responses),
            ):
                result = discover_sources.discover_documents(root, families=None, dry_run=False, limit=None)

            self.assertEqual(result, 0)
            discovered = load_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl")
            by_url = {row["source_url"]: row for row in discovered}

            self.assertIn(selector_url, by_url)
            self.assertIn(doc_url, by_url)
            self.assertEqual(by_url[doc_url]["year"], 2000)
            self.assertEqual(by_url[doc_url]["document_type"], "tasks")
            self.assertIn("html_container=true", by_url[selector_url]["notes"])

    def test_normalize_recovers_year_from_html_text_and_prefers_html_extension(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            row = make_download_row(
                root,
                name="history-page",
                raw_suffix=".bin",
                raw_text="<html><title>IAO page</title><p>II International Astronomy Olympiad</p></html>",
                txt_text="II International Astronomy Olympiad 1997",
                source_title="II International Astronomy Olympiad",
                source_url="https://example.org/iao/history",
                filename_original="history-page",
            )
            write_jsonl(root / "data" / "manifests" / "download_manifest.jsonl", [row])

            result = normalize_archive.normalize(root, families=None, dry_run=False, limit=None)

            self.assertEqual(result, 0)
            normalized = load_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl")
            self.assertEqual(len(normalized), 1)
            self.assertEqual(normalized[0]["year"], 1997)
            self.assertEqual(normalized[0]["extension"], "html")
            self.assertTrue(normalized[0]["filename_normalized"].endswith(".html"))
            self.assertIn("/1997/", normalized[0]["archive_path"])

    def test_normalize_skips_placeholder_and_container_html(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            placeholder = make_download_row(
                root,
                name="spbao-placeholder",
                raw_suffix=".html",
                raw_text="<html><p>К сожалению, у нас нет заданий за этот год</p></html>",
                txt_text="К сожалению, у нас нет заданий за этот год",
                source_id="spbao_year_class_pages",
                olympiad_family="spbao",
                year=2026,
                language="ru",
                source_url="https://example.org/spbao/2026/grade-5",
                notes="seed_page=true; source_kind=html",
            )
            container = make_download_row(
                root,
                name="ioaa-container",
                raw_suffix=".html",
                raw_text='<html><a href="archive.pdf">PDF</a></html>',
                txt_text="Problems from past IOAA",
                source_id="ioaa_problems",
                olympiad_family="ioaa",
                source_url="https://example.org/ioaa/archive",
                document_type="info",
                notes="seed_page=true; source_kind=html; html_container=true",
            )
            write_jsonl(root / "data" / "manifests" / "download_manifest.jsonl", [placeholder, container])

            result = normalize_archive.normalize(root, families=None, dry_run=False, limit=None)

            self.assertEqual(result, 0)
            normalized = load_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl")
            self.assertEqual(normalized, [])

    def test_normalize_keeps_real_html_task_page(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            row = make_download_row(
                root,
                name="iao-1999-page",
                raw_suffix=".html",
                raw_text="""
                <html>
                  <title>1999 Problems</title>
                  <h1>Problems</h1>
                  <p>Problem 1. Estimate the distance.</p>
                  <p>Problem 2. Compute the orbit.</p>
                </html>
                """,
                txt_text="1999 Problems Problem 1. Estimate the distance. Problem 2. Compute the orbit.",
                source_title="1999 Problems",
                source_url="https://example.org/iao/1999/problems.html",
                filename_original="problems.html",
            )
            write_jsonl(root / "data" / "manifests" / "download_manifest.jsonl", [row])

            result = normalize_archive.normalize(root, families=None, dry_run=False, limit=None)

            self.assertEqual(result, 0)
            normalized = load_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl")
            self.assertEqual(len(normalized), 1)
            self.assertEqual(normalized[0]["document_type"], "tasks")
            self.assertEqual(normalized[0]["extension"], "html")

    def test_normalize_prefers_direct_file_over_same_page_html(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            html_page_url = "https://example.org/2024/final.html"
            html_row = make_download_row(
                root,
                name="event-page",
                raw_suffix=".html",
                raw_text="""
                <html>
                  <title>2024 Final Tasks</title>
                  <p>Problem 1. First question.</p>
                  <p>Problem 2. Second question.</p>
                </html>
                """,
                txt_text="2024 Final Tasks Problem 1. First question. Problem 2. Second question.",
                source_id="example_archive",
                olympiad_family="iao",
                year=2024,
                stage_or_round="final",
                source_url=html_page_url,
                parent_page_url=html_page_url,
                source_title="2024 Final Tasks",
                filename_original="final.html",
            )
            pdf_path = root / "data" / "raw" / "event.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(b"%PDF-1.4\n%fake\n")
            pdf_row = {
                **html_row,
                "candidate_id": "event-pdf",
                "raw_path": str(pdf_path),
                "txt_path": "",
                "source_url": "https://example.org/2024/final.pdf",
                "filename_original": "final.pdf",
                "extension": "pdf",
            }
            write_jsonl(root / "data" / "manifests" / "download_manifest.jsonl", [html_row, pdf_row])

            result = normalize_archive.normalize(root, families=None, dry_run=False, limit=None)

            self.assertEqual(result, 0)
            normalized = load_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl")
            self.assertEqual(len(normalized), 1)
            self.assertEqual(normalized[0]["extension"], "pdf")

    def test_crawl_reuses_legacy_bin_for_drupal_pdf_url(self) -> None:
        url = "http://school.astro.spbu.ru/?q=system/files/10%20%D0%BA%D0%BB%D0%B0%D1%81%D1%81%20-%20%D1%80%D0%B5%D1%88%D0%B5%D0%BD%D0%B8%D1%8F_51.pdf"
        row = {
            "candidate_id": "spbao-pdf",
            "source_id": "spbao_official",
            "olympiad_family": "spbao",
            "year": 2025,
            "stage_or_round": "final",
            "language": "ru",
            "document_type": "tasks",
            "source_url": url,
            "source_domain": "school.astro.spbu.ru",
            "source_title": "10 класс - задачи и решения",
            "source_priority": 1,
            "source_role": "official",
            "parent_page_url": "http://school.astro.spbu.ru/?q=node/678",
            "parent_page_title": "Теоретический тур",
            "filename_original": "10 класс - решения_51.pdf",
            "extension": "pdf",
            "variant_tag": "official_combined",
            "round_detail": "theoretical",
            "notes": "",
            "seed_context": {"year": 2025, "stage_or_round": "final", "round_detail": "theoretical"},
        }

        class NoFetchHttpClient:
            def __init__(self, logger=None, dry_run: bool = False):
                self.logger = logger
                self.dry_run = dry_run

            def fetch(self, url: str) -> SimpleNamespace:
                raise AssertionError(f"Unexpected network fetch for {url}")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl", [row])
            legacy_raw_path = crawl_source.target_raw_path(root, row["source_id"], url, "bin")
            legacy_raw_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_raw_path.write_bytes(b"%PDF-1.4\n%legacy\n")

            with patch.object(crawl_source, "HttpClient", NoFetchHttpClient):
                result = crawl_source.crawl_documents(root, families=None, dry_run=False, limit=None)

            self.assertEqual(result, 0)
            downloaded = load_jsonl(root / "data" / "manifests" / "download_manifest.jsonl")
            self.assertEqual(len(downloaded), 1)
            self.assertEqual(downloaded[0]["status"], "existing")
            self.assertEqual(downloaded[0]["raw_path"], str(legacy_raw_path))
            self.assertEqual(downloaded[0]["content_type"], "application/pdf")
