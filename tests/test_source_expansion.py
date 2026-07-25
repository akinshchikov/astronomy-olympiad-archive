from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import build_indices
import crawl_source
import discover_sources
import normalize_archive
from utils.fs_utils import load_jsonl, write_jsonl
from utils.models import SourceDefinition


FIXTURES = Path(__file__).parent / "fixtures"


def response(url, text):
    return SimpleNamespace(final_url=url, status_code=200, text=text, content=text.encode(), headers={"Content-Type": "text/html"})


def client(pages, calls=None):
    class Client:
        def __init__(self, logger=None, dry_run=False): pass
        def fetch(self, url):
            if calls is not None: calls.append(url)
            return pages[url]
    return Client


class SourceExpansionTests(TestCase):
    def test_revision_suffixes_are_not_school_years_in_production_year_resolution(self):
        cases = {
            "usaaao_first_exam_sol_2025-1.pdf": 2025,
            "second_exam_2024-1.pdf": 2024,
            "usaaao_first_exam_2024-3.pdf": 2024,
        }
        for filename, expected in cases.items():
            self.assertEqual(discover_sources.usaaao_event_year(f"https://usaaao.org/wp-content/uploads/2025/09/{filename}", {}), expected)
        self.assertIsNone(discover_sources.czech_school_year("usaaao_first_exam_sol_2025-1.pdf"))

    def discover_rows(self, source, pages):
        with TemporaryDirectory() as tmp, patch.object(discover_sources, "SOURCE_DEFINITIONS", [source]), patch.object(
            discover_sources, "HttpClient", client(pages)
        ):
            root = Path(tmp)
            self.assertEqual(discover_sources.discover_documents(root, None, False, None), 0)
            return {row["source_url"]: row for row in load_jsonl(root / "data/manifests/discovered_documents.jsonl")}

    def test_ioaa_junior_year_page_and_combined_questions_answers(self):
        archive, year, combined = "https://ioaastrophysics.org/junior-ioaa/past-olympiads", "https://ioaastrophysics.org/junior-ioaa/past-olympiads/2025/", "https://ioaastrophysics.org/files/2025_questions_and_answers.pdf"
        source = SourceDefinition("ioaa_junior_official", "Junior", "ioaa_junior", "official", 1, "static", [archive], extras={"default_context": {"record_seed_page": False, "follow_second_hop": True, "max_follow_depth": 1}})
        rows = self.discover_rows(source, {archive: response(archive, f"<a href='{year}'>2025</a>"), year: response(year, f"<a href='{combined}'>Questions and Answers</a>")})
        self.assertEqual(rows[combined]["year"], 2025)
        self.assertEqual(rows[combined]["document_type"], "solutions")
        self.assertIn("extra_types=tasks,solutions", rows[combined]["notes"])

    def test_usaaao_round_contexts(self):
        page = "https://usaaao.org/resources/past-exams/"
        urls = [f"https://usaaao.org/{name}.pdf" for name in ("first", "nac", "third_theory", "third_practical_solution")]
        html = f"<h2>2026</h2><h3>First Round</h3><a href='{urls[0]}'>Exam</a><h3>NAC</h3><a href='{urls[1]}'>Test</a><h3>Third Exam</h3><a href='{urls[2]}'>Theory Exam</a><a href='{urls[3]}'>Practical Solution</a>"
        source = SourceDefinition("usaaao_past_exams", "USAAAO", "usaaao", "official", 1, "static", [page], extras={"default_context": {"record_seed_page": False}})
        rows = self.discover_rows(source, {page: response(page, html)})
        self.assertEqual(rows[urls[0]]["stage_or_round"], "first-round")
        self.assertEqual(rows[urls[1]]["stage_or_round"], "national")
        self.assertEqual((rows[urls[2]]["stage_or_round"], rows[urls[2]]["round_detail"]), ("selection", "theoretical"))
        self.assertEqual((rows[urls[3]]["stage_or_round"], rows[urls[3]]["round_detail"], rows[urls[3]]["document_type"]), ("selection", "practical", "solutions"))

    def test_authoritative_round_metadata_survives_existing_download_normalization(self):
        usaaao_page = "https://usaaao.org/resources/past-exams/"
        junior_archive = "https://ioaastrophysics.org/junior-ioaa/past-olympiads"
        junior_2024 = f"{junior_archive}/2024/"
        junior_2025 = f"{junior_archive}/2025/"
        inao_page = "https://olympiads.hbcse.tifr.res.in/how-to-prepare/past-papers/"
        czech_archive = "https://olympiada.astro.cz/archiv"
        czech_year = "https://olympiada.astro.cz/archiv/22-rocnik-2024-25"
        practice_exam = "https://usaaao.org/2015-practice-round-exam.pdf"
        practice_solutions = "https://usaaao.org/2015-practice-round-solutions.pdf"
        junior_questions = "https://ioaastrophysics.org/files/Junior_IOAA_2024_question_papers.pdf"
        junior_answers = "https://ioaastrophysics.org/files/Junior_IOAA_2024_answer_sheets_and_solutions.pdf"
        junior_combined = "https://ioaastrophysics.org/files/Junior_IOAA_2025_Questions_and_Answers.pdf"
        inao_senior = "https://hbcse.example/inaoSr2008-Q-S.pdf"
        contaminants = [
            "https://olympiada.astro.cz/f/detail/1786_IAO-2013-zadani.pdf",
            "https://olympiada.astro.cz/f/detail/1981_IAO-2011-zadani.pdf",
            "https://olympiada.astro.cz/f/detail/1890_IAO-2012-zadani.pdf",
            "https://olympiada.astro.cz/f/detail/2068_TZ-AO-Finale-200708.pdf",
        ]
        sources = [
            SourceDefinition("usaaao_past_exams", "USAAAO", "usaaao", "official", 1, "static", [usaaao_page], extras={"default_context": {"record_seed_page": False}}),
            SourceDefinition("ioaa_junior_official", "Junior", "ioaa_junior", "official", 1, "static", [junior_archive], extras={"default_context": {"record_seed_page": False, "follow_second_hop": True, "max_follow_depth": 1}}),
            SourceDefinition("inao_hbcse_past_papers", "INAO", "inao", "official", 1, "static", [inao_page], extras={"default_context": {"record_seed_page": False}}),
            SourceDefinition("czech_astronomy_official", "Czech", "czech_astronomy", "official", 1, "static", [czech_archive], extras={"default_context": {"record_seed_page": False, "follow_second_hop": True, "max_follow_depth": 1}}),
        ]
        pages = {
            usaaao_page: response(usaaao_page, f"<h2>2015</h2><h3>NAC</h3><h3>Practice Round</h3><a href='{practice_exam}'>Exam</a><a href='{practice_solutions}'>Solutions</a>"),
            junior_archive: response(junior_archive, f"<a href='{junior_2024}'>2024</a><a href='{junior_2025}'>2025</a>"),
            junior_2024: response(junior_2024, f"<a href='{junior_questions}'>Question papers</a><a href='{junior_answers}'>Answer sheets and solutions</a>"),
            junior_2025: response(junior_2025, f"<a href='{junior_combined}'>Questions and Answers</a>"),
            inao_page: response(inao_page, f"<table><tr><td>2008 INAO Astronomy Junior</td><td><a href='{inao_senior}'>Solution</a></td></tr></table>"),
            czech_archive: response(czech_archive, f"<a href='{czech_year}'>22. ročník 2024/25</a>"),
            czech_year: response(czech_year, "<h2>Ústřední kolo</h2>" + "".join(f"<a href='{url}'>Zadání</a>" for url in contaminants)),
        }
        with TemporaryDirectory() as tmp, patch.object(discover_sources, "SOURCE_DEFINITIONS", sources), patch.object(discover_sources, "HttpClient", client(pages)):
            root = Path(tmp)
            self.assertEqual(discover_sources.discover_documents(root, None, False, None), 0)
            discovered = load_jsonl(root / "data/manifests/discovered_documents.jsonl")
            discovered_urls = {row["source_url"] for row in discovered}
            self.assertTrue({practice_exam, practice_solutions, junior_questions, junior_answers, junior_combined, inao_senior}.issubset(discovered_urls))
            self.assertTrue(set(contaminants).isdisjoint(discovered_urls))
            for row in discovered:
                raw = crawl_source.target_raw_path(root, row["source_id"], row["source_url"], row["extension"])
                raw.parent.mkdir(parents=True, exist_ok=True)
                raw.write_bytes(b"fixture PDF")
            self.assertEqual(crawl_source.crawl_documents(root, None, False, None), 0)
            self.assertEqual(normalize_archive.normalize(root, None, False, None), 0)
            normalized = {row["filename_original"]: row for row in load_jsonl(root / "data/manifests/normalized_entries.jsonl")}
            expected = {
                "2015-practice-round-exam.pdf": (2015, "practice", None, "tasks", ["tasks"]),
                "2015-practice-round-solutions.pdf": (2015, "practice", None, "solutions", ["solutions"]),
                "Junior_IOAA_2024_question_papers.pdf": (2024, "combined", "theoretical_and_observational", "tasks", ["tasks"]),
                "Junior_IOAA_2024_answer_sheets_and_solutions.pdf": (2024, "combined", "theoretical_and_observational", "solutions", ["solutions"]),
                "Junior_IOAA_2025_Questions_and_Answers.pdf": (2025, "combined", "theoretical_and_observational", "solutions", ["tasks", "solutions"]),
                "inaoSr2008-Q-S.pdf": (2008, "national", "senior", "solutions", ["tasks", "solutions"]),
            }
            for filename, values in expected.items():
                with self.subTest(filename=filename):
                    row = normalized[filename]
                    self.assertEqual((row["year"], row["stage_or_round"], row["round_detail"], row["document_type"], row["logical_document_types"]), values)
            self.assertEqual(normalized["inaoSr2008-Q-S.pdf"]["redistribution_status"], "explicit-no-redistribution")
            self.assertTrue(set(contaminants).isdisjoint({row["source_url"] for row in normalized.values()}))
            for filename in expected:
                row = normalized[filename]
                metadata = Path(row["archive_path"]).parents[1] / "info" / "event-metadata.json"
                self.assertIn(filename, {item["filename_original"] for item in __import__("json").loads(metadata.read_text(encoding="utf-8"))})

    def test_inao_filters_subjects_languages_and_redistribution(self):
        page, en, hi, sol, physics = "https://olympiads.hbcse.tifr.res.in/how-to-prepare/past-papers/", "https://hbcse/INAO-QP-E.pdf", "https://hbcse/INAO-QP-H.pdf", "https://hbcse/INAO-Solution.pdf", "https://hbcse/INPhO-QP-E.pdf"
        html = f"<table><tr><td>2025 INAO Astronomy</td><td><a href='{en}'>QP(E)</a></td><td><a href='{hi}'>QP(H)</a></td><td><a href='{sol}'>Solutions</a></td></tr><tr><td>2025 INPhO Physics</td><td><a href='{physics}'>QP(E)</a></td></tr></table>"
        source = SourceDefinition("inao_hbcse_past_papers", "INAO", "inao", "official", 1, "static", [page], extras={"default_context": {"record_seed_page": False}})
        rows = self.discover_rows(source, {page: response(page, html)})
        self.assertNotIn(physics, rows)
        self.assertEqual((rows[en]["language"], rows[hi]["language"], rows[sol]["document_type"]), ("en", "hi", "solutions"))
        self.assertIn("redistribution_status=explicit-no-redistribution", rows[sol]["notes"])

    def test_czech_school_year_category_and_extensionless_file(self):
        archive, year_page, task = "https://olympiada.astro.cz/archiv", "https://olympiada.astro.cz/archiv/22-rocnik-2024-25", "https://olympiada.astro.cz/f/detail/skolni-zadani?hash=abc"
        source = SourceDefinition("czech_astronomy_official", "Czech", "czech_astronomy", "official", 1, "static", [archive], extras={"default_context": {"record_seed_page": False, "follow_second_hop": True, "max_follow_depth": 1}})
        rows = self.discover_rows(source, {archive: response(archive, f"<a href='{year_page}'>22. ročník 2024/25</a>"), year_page: response(year_page, f"<h2>Školní kolo</h2><h3>Kategorie AB</h3><a href='{task}'>Zadání</a>")})
        self.assertEqual((rows[task]["year"], rows[task]["stage_or_round"], rows[task]["extension"]), (2025, "school", "pdf"))
        self.assertEqual(rows[task]["seed_context"]["category"], "AB")

    def test_gecaa_classification_and_core_ioaa_leak_prevention(self):
        page = "https://gecaa.ee/competition-problems-and-solutions/"
        urls = [f"https://gecaa.ee/{name}.pdf" for name in ("Theory_2020", "Data_Analysis_solutions", "Observation", "Team_PIXIE_Solution", "Student_User_Guide")]
        source = SourceDefinition("gecaa_official_archive", "GeCAA", "gecaa", "official", 1, "static", [page], extras={"default_context": {"record_seed_page": False, "year": 2020}})
        rows = self.discover_rows(source, {page: response(page, "".join(f"<a href='{url}'>{url.rsplit('/', 1)[-1]}</a>" for url in urls))})
        self.assertEqual([rows[url]["stage_or_round"] for url in urls[:4]], ["theoretical", "data-analysis", "observational", "team"])
        self.assertEqual((rows[urls[1]]["document_type"], rows[urls[4]]["document_type"]), ("solutions", "instructions"))
        core = {"source_id": "ioaa_problems", "olympiad_family": "ioaa", "source_role": "official", "source_priority": 1, "url": page, "context": {}}
        self.assertFalse(discover_sources.passes_source_specific_link_filter(core, "GeCAA Theory", urls[0]))
        self.assertFalse(discover_sources.passes_source_specific_link_filter(core, "Junior IOAA", "https://ioaastrophysics.org/junior-ioaa/past-olympiads/2025/"))

    def test_ioaa_and_gecaa_link_filters_cover_all_combined_branches(self):
        def seed(source_id):
            return {"source_id": source_id, "olympiad_family": "ioaa", "source_role": "official", "source_priority": 1, "url": "https://example.test", "context": {}}

        core = seed("ioaa_problems")
        self.assertFalse(discover_sources.passes_source_specific_link_filter(core, "Junior IOAA", "https://example.test/junior-ioaa/past-olympiads/2025/"))
        self.assertFalse(discover_sources.passes_source_specific_link_filter(core, "GeCAA theory", "https://example.test/gecaa-theory.pdf"))
        self.assertTrue(discover_sources.passes_source_specific_link_filter(core, "IOAA theoretical", "https://example.test/theory.pdf"))

        junior = seed("ioaa_junior_official")
        self.assertTrue(discover_sources.passes_source_specific_link_filter(junior, "2025", "https://example.test/junior-ioaa/past-olympiads/2025/"))
        self.assertTrue(discover_sources.passes_source_specific_link_filter(junior, "Question paper", "https://example.test/questions.pdf"))
        self.assertTrue(discover_sources.passes_source_specific_link_filter(junior, "Solutions", "https://example.test/solutions.pdf"))
        self.assertFalse(discover_sources.passes_source_specific_link_filter(junior, "Results", "https://example.test/results.pdf"))

        gecaa = seed("gecaa_official_archive")
        for title, url in (("Theoretical", "theory.pdf"), ("Data analysis", "data-analysis.pdf"), ("Observational", "observation.pdf")):
            with self.subTest(title=title):
                self.assertTrue(discover_sources.passes_source_specific_link_filter(gecaa, title, f"https://example.test/{url}"))
        for title, url in (("Circular", "circular.pdf"), ("Regulations", "regulations.pdf"), ("Results", "results.pdf")):
            with self.subTest(title=title):
                self.assertFalse(discover_sources.passes_source_specific_link_filter(gecaa, title, f"https://example.test/{url}"))

    def test_struve_override_is_link_only_and_history_config_is_valid(self):
        seed = {
            "source_id": "struve_astroedu_archive", "olympiad_family": "struve", "source_role": "official",
            "source_priority": 1, "url": "https://astroedu.ru/struve/problems", "context": {},
        }
        # A seed page has no link href and must therefore not invoke the
        # filename override. The direct-link assertion is covered below.
        page = discover_sources.record_seed_page(seed, "Struve archive")
        self.assertEqual(page["source_url"], seed["url"])
        self.assertEqual(page["access_mode"], "download")
        history = build_indices.load_family_history(Path("."))
        self.assertEqual(history["struve"]["not_held_components"][0]["stage_or_round"], "final")

    def test_struve_context_and_uts_access_mode(self):
        url = "https://astroedu.ru/struve/problems"
        html = (FIXTURES / "struve_archive.html").read_text(encoding="utf-8")
        source = SourceDefinition("struve_astroedu_archive", "Struve", "struve", "official", 1, "static", [url], extras={"default_context": {"record_seed_page": False}})
        with TemporaryDirectory() as tmp, patch.object(discover_sources, "SOURCE_DEFINITIONS", [source]), patch.object(discover_sources, "HttpClient", client({url: response(url, html)})):
            discover_sources.discover_documents(Path(tmp), None, False, None)
            rows = {row["source_url"]: row for row in load_jsonl(Path(tmp) / "data/manifests/discovered_documents.jsonl")}
        task = rows["https://astroedu.ru/assets/problems/struve/2026/struve-2026-reg-prob-day1-7.pdf"]
        self.assertEqual((task["year"], task["stage_or_round"], task["round_detail"], task["document_type"], task["language"]), (2026, "regional", "day1", "tasks", "ru"))
        self.assertEqual(rows["https://uts.astroedu.ru/synthetic-struve-2026-grade-7"]["access_mode"], "discovery_only")

    def test_mao_and_russia_context(self):
        mao_url, team_url = "https://mosastro.olimpiada.ru/tasks", "https://astroedu.ru/hq/problems/"
        mao_html = (FIXTURES / "mao_archive.html").read_text(encoding="utf-8")
        team_html = (FIXTURES / "russia_team_archive.html").read_text(encoding="utf-8")
        sources = [SourceDefinition("mao_official_archive", "MAO", "mao", "official", 1, "static", [mao_url], extras={"default_context": {"record_seed_page": False}}), SourceDefinition("russia_team_qual_archive", "HQ", "russia_team_qual", "official", 1, "static", [team_url], extras={"default_context": {"record_seed_page": False}})]
        with TemporaryDirectory() as tmp, patch.object(discover_sources, "SOURCE_DEFINITIONS", sources), patch.object(discover_sources, "HttpClient", client({mao_url: response(mao_url, mao_html), team_url: response(team_url, team_html)})):
            discover_sources.discover_documents(Path(tmp), None, False, None)
            rows = {row["source_url"]: row for row in load_jsonl(Path(tmp) / "data/manifests/discovered_documents.jsonl")}
        combined = rows["https://mosastro.olimpiada.ru/upload/files/mos2026/mos_astro_2026_teor_7_ans.pdf"]
        self.assertEqual((combined["year"], combined["stage_or_round"], combined["document_type"]), (2026, "theoretical", "solutions"))
        self.assertIn("extra_types=tasks,solutions", combined["notes"])
        blitz = rows["https://uts.astroedu.ru/synthetic-q26s1-blitz"]
        self.assertEqual((blitz["year"], blitz["stage_or_round"], blitz["round_detail"], blitz["access_mode"]), (2026, "test", "blitz-Q26S1", "discovery_only"))

    def test_explicit_access_mode_skips_http(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); manifest = root / "data/manifests/discovered_documents.jsonl"; manifest.parent.mkdir(parents=True)
            write_jsonl(manifest, [{"source_url": "https://uts.astroedu.ru/x", "source_id": "x", "olympiad_family": "struve", "access_mode": "discovery_only", "notes": ""}])
            calls = []
            with patch.object(crawl_source, "HttpClient", client({}, calls)):
                self.assertEqual(crawl_source.crawl_documents(root, None, False, None), 0)
            self.assertEqual(calls, [])
