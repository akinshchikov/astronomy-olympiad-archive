from pathlib import Path
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import urllib.error
from unittest import TestCase
from unittest.mock import patch

import build_indices
import crawl_source
import discover_sources
import normalize_archive
from utils.fs_utils import load_jsonl, write_jsonl
from utils.metadata import thai_buddhist_year_to_gregorian
from utils.models import SourceDefinition
from utils.source_configs import SOURCE_DEFINITIONS


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
    def test_batch_c_runtime_sources_match_active_audit_and_keep_deferred_out(self):
        runtime = {source.source_id: source.olympiad_family for source in SOURCE_DEFINITIONS}
        self.assertIn("olaa_official_archive", runtime)
        self.assertEqual(runtime["bangladesh_bao_official"], "bangladesh_bao")
        self.assertEqual(runtime["sri_lanka_junior_ipsl_official"], "sri_lanka_junior_astronomy")
        self.assertNotIn("apao_issp_official", runtime)
        self.assertNotIn("taiwan_astronomy_deferred_reference", runtime)
        self.assertNotIn("hong_kong_astronomy_space_museum", runtime)

    def test_batch_c_negative_filters_preserve_lineages_and_reject_non_papers(self):
        def seed(source_id, family):
            return {"source_id": source_id, "olympiad_family": family, "source_role": "official", "source_priority": 1, "url": "https://example.test", "context": {}}

        cases = [
            (seed("caao_official_past_contests", "caao"), "IOAA 2025 theory", "https://caao.ca/ioaa-2025.pdf", False),
            (seed("caao_official_past_contests", "caao"), "Senior contest problems", "https://caao.ca/contest.pdf", True),
            (seed("china_cnao_beijing_planetarium_official", "china_cnao"), "Provincial feeder", "https://bjp.org.cn/provincial.pdf", False),
            (seed("iran_astronomy_irysc_mirror", "iran_astronomy"), "Mock course", "https://irysc.com/mock.pdf", False),
            (seed("macao_astronomy_sepam_official", "macao_astronomy"), "CNAO preparation", "https://sepam.org/cnao.pdf", False),
            (seed("macao_astronomy_sepam_official", "macao_astronomy"), "2024预赛A卷试题及答案", "https://sepam.org/wp-content/uploads/2026/03/2024.pdf", True),
            (seed("macao_astronomy_sepam_official", "macao_astronomy"), "获奖名单", "https://sepam.org/wp-content/uploads/results.pdf", False),
            (seed("singapore_astronomy_official", "singapore_astronomy"), "Olympiad paper", "https://drive.google.com/file/d/1/view.pdf", True),
            (seed("singapore_astronomy_official", "singapore_astronomy"), "Olympiad paper", "https://example.net/paper.pdf", False),
            (seed("nzoaa_official", "nzoaa"), "Question Paper", "https://drive.google.com/file/d/nzoaa/view", True),
            (seed("nzoaa_official", "nzoaa"), "IOAA preparation", "https://ioaastrophysics.org/paper.pdf", False),
            (seed("nzoaa_official", "nzoaa"), "USAAAO preparation", "https://usaaao.org/paper.pdf", False),
            (seed("sri_lanka_ipsl_official", "sri_lanka_astronomy"), "Senior paper", "https://ipsl.lk/documents/astro/astro-test-2011_Sinhala.pdf", True),
            (seed("sri_lanka_ipsl_official", "sri_lanka_astronomy"), "Junior paper", "https://ipsl.lk/documents/astro/SLJAO-test-2011_Sinhala.pdf", False),
            (seed("sri_lanka_junior_ipsl_official", "sri_lanka_junior_astronomy"), "Junior paper", "https://ipsl.lk/documents/astro/SLJAO-test-2011_Sinhala.pdf", True),
            (seed("sri_lanka_junior_ipsl_official", "sri_lanka_junior_astronomy"), "Navigation", "https://ipsl.lk/physics-olympiad/", False),
            (seed("slovenia_astronomy_dmfa_official", "slovenia_astronomy"), "As_Drzavno_2024.pdf", "https://www.dmfa.si/Tekmovanja/GetPDF.ashx?src=As_Drzavno_2024.pdf", True),
            (seed("slovenia_astronomy_primary_dmfa_official", "slovenia_astronomy_primary"), "As_Drzavno_2024.pdf", "https://www.dmfa.si/Tekmovanja/GetPDF.ashx?src=As_Drzavno_2024.pdf", False),
            (seed("slovenia_astronomy_primary_dmfa_official", "slovenia_astronomy_primary"), "AsOS_Solsko_2024.pdf", "https://www.dmfa.si/Tekmovanja/GetPDF.ashx?src=AsOS_Solsko_2024.pdf", True),
            (seed("slovenia_utrinek_dmfa_official", "slovenia_utrinek"), "AsOSU_Drzavno_2024.pdf", "https://www.dmfa.si/Tekmovanja/GetPDF.ashx?src=AsOSU_Drzavno_2024.pdf", True),
        ]
        for candidate, text, url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(discover_sources.passes_source_specific_link_filter(candidate, text, url), expected)

        archive_seed = seed("olaa_official_archive", "olaa")
        self.assertTrue(discover_sources.should_record_seed_link(archive_seed, "Past contests 2025", "https://example.test/past-contests/2025"))
        self.assertFalse(discover_sources.should_record_seed_link(archive_seed, "Latest news", "https://example.test/news"))

    def test_thai_buddhist_era_conversion_is_explicit_and_bounded(self):
        self.assertEqual(thai_buddhist_year_to_gregorian(2567, explicit_buddhist_era=True), 2024)
        self.assertEqual(thai_buddhist_year_to_gregorian(2024, explicit_buddhist_era=True), 2024)
        self.assertEqual(thai_buddhist_year_to_gregorian(2567, explicit_buddhist_era=False), 2567)

    def test_olaa_official_drive_links_and_baao_paper_containers_are_bounded(self):
        olaa_page = "https://www.olaa-astro.org/p/pruebas_3.html"
        drive = "https://drive.google.com/file/d/olaa-2024/view"
        olaa = SourceDefinition("olaa_official_archive", "OLAA", "olaa", "official", 1, "static", [olaa_page], extras={"default_context": {"record_seed_page": False}})
        olaa_rows = self.discover_rows(olaa, {olaa_page: response(olaa_page, f"<h2>2024 Problems</h2><a href='{drive}'>Problems and solutions</a>")})
        self.assertEqual(olaa_rows[drive]["extension"], "pdf")
        self.assertEqual(olaa_rows[drive]["olympiad_family"], "olaa")
        self.assertEqual(olaa_rows[drive]["access_mode"], "discovery_only")
        self.assertEqual(crawl_source.public_download_url(drive), "https://drive.usercontent.google.com/download?id=olaa-2024&export=download")
        self.assertEqual(crawl_source.public_download_url("https://example.test/provas/nível-1.pdf"), "https://example.test/provas/n%C3%ADvel-1.pdf")
        self.assertEqual(crawl_source.public_download_url("https://example.test/foo%20bar/nível.pdf?download=1&lang=pt#page"), "https://example.test/foo%20bar/n%C3%ADvel.pdf?download=1&lang=pt#page")
        self.assertEqual(crawl_source.public_download_url("https://example.test/plain.pdf"), "https://example.test/plain.pdf")
        self.assertEqual(crawl_source.public_download_url("https://example.test/provas/n%C3%ADvel-1.pdf"), "https://example.test/provas/n%C3%ADvel-1.pdf")
        self.assertFalse(crawl_source.response_matches_extension("pdf", "text/html", b"<html>preview</html>"))
        self.assertTrue(crawl_source.response_matches_extension("pdf", "application/pdf", b"%PDF-1.7\n"))

        baao_page, container, paper = "https://www.bpho.org.uk/baao/", "https://www.bpho.org.uk/baao/Papers/R1/", "https://www.bpho.org.uk/baao/Papers/R1/BAAO-2024.pdf"
        baao = SourceDefinition("baao_bpho_official", "BAAO", "baao", "official", 1, "static", [baao_page], extras={"default_context": {"record_seed_page": False, "follow_second_hop": True, "max_follow_depth": 1}})
        rows = self.discover_rows(baao, {baao_page: response(baao_page, f"<a href='{container}'>Round 1 papers</a><a href='https://www.bpho.org.uk/Papers/R1/'>Physics</a>"), container: response(container, f"<h2>2024</h2><a href='{paper}'>BAAO Round 1 Problems</a>")})
        self.assertIn(paper, rows)
        self.assertNotIn("https://www.bpho.org.uk/Papers/R1/", rows)

    def test_nzoaa_official_drive_papers_keep_year_and_reject_html_containers(self):
        page = "https://www.nzoaa.com/past-papers-1"
        question = "https://drive.google.com/file/d/questions/view"
        marking = "https://drive.google.com/file/d/marking/view"
        source = SourceDefinition("nzoaa_official", "NZOAA", "nzoaa", "official", 2, "static", [page], extras={"default_context": {"record_seed_page": False}})
        rows = self.discover_rows(source, {page: response(page, f"<h2>2024 Past Paper</h2><a href='{question}'>Question Paper</a><a href='{marking}'>Markscheme</a><a href='/past-papers-1'>Past Papers</a><a href='https://ioaastrophysics.org/2024.pdf'>IOAA preparation</a>")})
        self.assertEqual(set(rows), {question, marking})
        self.assertEqual((rows[question]["year"], rows[question]["document_type"]), (2024, "tasks"))
        self.assertEqual((rows[marking]["year"], rows[marking]["document_type"]), (2024, "marking"))

    def test_nepal_sample_papers_are_tasks_with_unknown_year_not_eligibility_dates(self):
        page = "https://www.nepalastronomicalsociety.org/projects/olympiad/"
        junior, senior = "http://bit.ly/junior-paper", "http://bit.ly/senior-paper"
        source = SourceDefinition("nepal_astronomy_naso_official", "NASO", "nepal_astronomy", "official", 2, "static", [page], extras={"default_context": {"record_seed_page": False}})
        html = f"Students born after 2010 are Junior. <h2>Sample Papers</h2>Click here to download the past paper for Junior Category <a href='{junior}'>Click here</a> Click here to download the past paper for senior category <a href='{senior}'>Click here</a>"
        rows = self.discover_rows(source, {page: response(page, html)})
        self.assertEqual(set(rows), {junior, senior})
        self.assertTrue(all(row["year"] is None and row["document_type"] == "tasks" and row["stage_or_round"] == "practice" for row in rows.values()))
        self.assertEqual({row["round_detail"] for row in rows.values()}, {"sample-junior", "sample-senior"})

    def test_thailand_form_cards_convert_explicit_buddhist_year_and_stay_discovery_only(self):
        page = "https://www.posn.or.th/projects/academic-olympiad/ao/examination/"
        source = SourceDefinition("thailand_astronomy_posn_official", "POSN", "thailand_astronomy", "official", 1, "static", [page], extras={"default_context": {"record_seed_page": False}})
        html = '<div class="exam-item" data-exam-id="2682"><div><h3><span class="exam-title">ข้อสอบดาราศาสตร์ ปี 2560</span></h3><span class="exam-categories">ข้อสอบดาราศาสตร์โอลิมปิกวิชาการระดับชาติ</span></div></div></div>'
        rows = self.discover_rows(source, {page: response(page, html)})
        row = next(iter(rows.values()))
        self.assertEqual((row["year"], row["document_type"], row["access_mode"]), (2017, "tasks", "discovery_only"))
        self.assertIn("official_form_gated_download", row["notes"])

    def test_cnao_and_iran_filters_keep_cnao_boundary_and_mirror_role(self):
        cn = {"source_id": "china_cnao_beijing_planetarium_official", "olympiad_family": "china_cnao", "source_role": "official", "source_priority": 1, "url": "https://www.bjp.org.cn/qgzxstwzsjs/", "context": {}}
        iran = {"source_id": "iran_astronomy_irysc_mirror", "olympiad_family": "iran_astronomy", "source_role": "mirror", "source_priority": 2, "url": "https://www.irysc.com/", "context": {}}
        self.assertTrue(discover_sources.passes_source_specific_link_filter(cn, "2024 CNAO final questions", "https://www.bjp.org.cn/cnao-2024.pdf"))
        self.assertFalse(discover_sources.passes_source_specific_link_filter(cn, "2024 provincial feeder", "https://www.bjp.org.cn/provincial-2024.pdf"))
        self.assertFalse(discover_sources.passes_source_specific_link_filter(iran, "Astronomy Olympiad mock course", "https://www.irysc.com/mock.pdf"))
        paper = discover_sources.build_candidate_entry(iran, href="https://www.irysc.com/iran-astronomy-olympiad-2024.pdf", link_text="Iran Astronomy Olympiad 2024 questions", page_title="", parent_page_url=iran["url"], parent_page_title="", context={})
        self.assertEqual((paper["source_role"], paper["olympiad_family"]), ("mirror", "iran_astronomy"))

    def test_iao_hosted_ioaa_papers_keep_the_existing_ioaa_family(self):
        self.assertEqual(discover_sources.infer_family("iao", "https://fizmat.space/files/IOAA-2021.pdf"), "ioaa")
        self.assertEqual(discover_sources.infer_family("iao", "https://www.issp.ac.ru/iao/2021/index.html"), "iao")
        self.assertEqual(discover_sources.infer_family("caao", "IOAA preparation link"), "caao")

    def test_caao_filename_metadata_is_task_paper_and_ioaa_is_excluded(self):
        page, paper, ioaa = "https://caao.ca/past-contests/", "https://caao.ca/wp-content/uploads/2023/CAAO-2023-1.pdf", "https://caao.ca/wp-content/uploads/2023/IOAA-2023.pdf"
        source = SourceDefinition("caao_official_past_contests", "CAAO", "caao", "official", 1, "static", [page], extras={"default_context": {"record_seed_page": False}})
        rows = self.discover_rows(source, {page: response(page, f"<a href='{paper}'>2023</a><a href='{ioaa}'>IOAA 2023</a>")})
        self.assertEqual((rows[paper]["document_type"], rows[paper]["stage_or_round"], rows[paper]["year"]), ("tasks", "national", 2023))
        self.assertNotIn(ioaa, rows)

    def test_bulgaria_and_brazil_official_filename_metadata(self):
        bulgaria = {"source_id": "bulgaria_astronomy_official", "olympiad_family": "bulgaria_astronomy", "source_role": "official", "source_priority": 1, "url": "https://astro-olymp.org/", "context": {}}
        brazil = {"source_id": "brazil_oba_official", "olympiad_family": "brazil_oba", "source_role": "official", "source_priority": 1, "url": "https://sistema.oba.org.br/", "context": {}}
        task = discover_sources.build_candidate_entry(bulgaria, href="https://astro-olymp.org/wp-content/uploads/2026/05/26-III-78.pdf", link_text="", page_title="", parent_page_url=bulgaria["url"], parent_page_title="", context={})
        answer = discover_sources.build_candidate_entry(bulgaria, href="https://astro-olymp.org/wp-content/uploads/2026/05/a26-III-78.pdf", link_text="", page_title="", parent_page_url=bulgaria["url"], parent_page_title="", context={})
        prova = discover_sources.build_candidate_entry(brazil, href="https://sistema.oba.org.br/2000_prova_niv3_oba.pdf", link_text="", page_title="", parent_page_url=brazil["url"], parent_page_title="", context={})
        gabarito = discover_sources.build_candidate_entry(brazil, href="https://sistema.oba.org.br/2000_gbniv3_oba.pdf", link_text="", page_title="", parent_page_url=brazil["url"], parent_page_title="", context={})
        container = discover_sources.build_candidate_entry(brazil, href="https://sistema.oba.org.br/site/?p=conteudo&idcat=9&pag=conteudo&m=s", link_text="Provas e Gabaritos", page_title="", parent_page_url=brazil["url"], parent_page_title="", context={})
        self.assertEqual((task["stage_or_round"], task["document_type"]), ("national", "tasks"))
        self.assertEqual(answer["document_type"], "solutions")
        self.assertEqual((prova["document_type"], prova["round_detail"]), ("tasks", "level-3"))
        self.assertEqual(gabarito["document_type"], "solutions")
        self.assertEqual(container["access_mode"], "discovery_only")
        self.assertIn("official_archive_container", container["notes"])

    def test_sri_lanka_lineages_and_language_variants_stay_separate(self):
        senior = {"source_id": "sri_lanka_ipsl_official", "olympiad_family": "sri_lanka_astronomy", "source_role": "official", "source_priority": 1, "url": "https://ipsl.lk/astronomy-olympiad/", "context": {}}
        junior = {**senior, "source_id": "sri_lanka_junior_ipsl_official", "olympiad_family": "sri_lanka_junior_astronomy"}
        senior_paper = discover_sources.build_candidate_entry(senior, href="https://ipsl.lk/documents/astro/astro-test-2011_Sinhala.pdf", link_text="", page_title="", parent_page_url=senior["url"], parent_page_title="", context={})
        junior_paper = discover_sources.build_candidate_entry(junior, href="https://ipsl.lk/documents/astro/SLJAO-test-2011_Tamil.pdf", link_text="", page_title="", parent_page_url=junior["url"], parent_page_title="", context={})
        self.assertEqual((senior_paper["olympiad_family"], senior_paper["document_type"], senior_paper["language"]), ("sri_lanka_astronomy", "tasks", "si"))
        self.assertEqual((junior_paper["olympiad_family"], junior_paper["document_type"], junior_paper["language"]), ("sri_lanka_junior_astronomy", "tasks", "ta"))

    def test_croatia_azoo_search_is_astronomy_test_only_and_keeps_stage_context(self):
        astronomy_post = "https://www.azoo.hr/natjecanja-i-smotre-arhiva/testovi-i-rjesenja-sa-skolske-razine-natjecanja-iz-astronomije-2024-2025/"
        unrelated_post = "https://www.azoo.hr/natjecanja-i-smotre-arhiva/testovi-i-rjesenja-sa-skolske-razine-natjecanja-iz-biologije-2024-2025/"
        links = discover_sources.croatia_azoo_search_links(json.dumps([
            {"subtype": "natjecanja-i-smotre", "title": "Testovi i rješenja sa školske razine Natjecanja iz astronomije 2024./2025.", "url": astronomy_post},
            {"subtype": "natjecanja-i-smotre", "title": "Testovi i rješenja sa školske razine Natjecanja iz biologije 2024./2025.", "url": unrelated_post},
        ]))
        self.assertEqual([link["href"] for link in links], [astronomy_post])
        seed = {"source_id": "croatia_astronomy_azoo_official", "olympiad_family": "croatia_astronomy", "source_role": "official", "source_priority": 1, "url": astronomy_post, "context": {}}
        task = discover_sources.build_candidate_entry(seed, href="https://www.azoo.hr/wp-content/uploads/2025/02/test.pdf", link_text="Test", page_title=links[0]["text"], parent_page_url=astronomy_post, parent_page_title=links[0]["text"], context={})
        solution = discover_sources.build_candidate_entry(seed, href="https://www.azoo.hr/wp-content/uploads/2025/02/rjesenja.pdf", link_text="Rješenja", page_title=links[0]["text"], parent_page_url=astronomy_post, parent_page_title=links[0]["text"], context={})
        self.assertEqual((task["stage_or_round"], task["document_type"], task["language"]), ("school", "tasks", "hr"))
        self.assertEqual((solution["stage_or_round"], solution["document_type"]), ("school", "solutions"))

    def test_terminal_failure_status_is_limited_to_durable_outcomes(self):
        self.assertEqual(crawl_source.terminal_failure_status(urllib.error.HTTPError("https://example.test/a.pdf", 404, "missing", {}, None)), "http_404")
        self.assertEqual(crawl_source.terminal_failure_status(urllib.error.HTTPError("https://example.test/a.pdf", 410, "gone", {}, None)), "http_410")
        self.assertIsNone(crawl_source.terminal_failure_status(urllib.error.HTTPError("https://example.test/a.pdf", 503, "busy", {}, None)))
        self.assertIsNone(crawl_source.terminal_failure_status(TimeoutError("slow")))

    def test_slovenia_dmfa_archives_preserve_lineage_stage_and_combined_semantics(self):
        source = {"source_id": "slovenia_astronomy_primary_dmfa_official", "olympiad_family": "slovenia_astronomy_primary", "source_role": "official", "source_priority": 1, "url": "https://www.dmfa.si/tekmovanja/AsOS/ArhivNalog.aspx", "context": {}}
        row = discover_sources.build_candidate_entry(source, href="https://www.dmfa.si/Tekmovanja/GetPDF.ashx?src=AsOS_Drzavno_2024.pdf", link_text="AsOS_Drzavno_2024.pdf", page_title="Arhiv tekmovalnih nalog", parent_page_url=source["url"], parent_page_title="Arhiv tekmovalnih nalog", context={})
        self.assertEqual((row["olympiad_family"], row["year"], row["stage_or_round"], row["language"]), ("slovenia_astronomy_primary", 2024, "state", "sl"))
        self.assertEqual((row["document_type"], row["logical_document_types"], row["extension"]), ("solutions", ["tasks", "solutions"], "pdf"))

    def test_revision_suffixes_are_not_school_years_in_production_year_resolution(self):
        cases = {
            "usaaao_first_exam_sol_2025-1.pdf": 2025,
            "second_exam_2024-1.pdf": 2024,
            "usaaao_first_exam_2024-3.pdf": 2024,
        }
        for filename, expected in cases.items():
            self.assertEqual(discover_sources.usaaao_event_year(f"https://usaaao.org/wp-content/uploads/2025/09/{filename}", {}), expected)
            self.assertIsNone(discover_sources.czech_school_year("usaaao_first_exam_sol_2025-1.pdf"))

    def test_failed_source_refresh_retains_previous_candidate_snapshot(self):
        page = "https://example.test/archive"
        source = SourceDefinition("test_archive", "Test", "test_family", "official", 1, "static", [page], extras={"default_context": {"record_seed_page": False}})
        previous = discover_sources.build_candidate_entry(
            {"source_id": source.source_id, "olympiad_family": source.olympiad_family, "source_role": "official", "source_priority": 1, "context": {}},
            href="https://example.test/2024-paper.pdf", link_text="2024 paper", page_title="Archive", parent_page_url=page, parent_page_title="Archive", context={},
        )

        class FailingClient:
            def __init__(self, logger=None, dry_run=False): pass
            def fetch(self, url): raise OSError("temporary DNS failure")

        with TemporaryDirectory() as tmp, patch.object(discover_sources, "SOURCE_DEFINITIONS", [source]), patch.object(discover_sources, "HttpClient", FailingClient):
            root = Path(tmp)
            write_jsonl(root / "data/manifests/discovered_documents.jsonl", [previous])
            self.assertEqual(discover_sources.discover_documents(root, {"test_family"}, False, None), 0)
            self.assertEqual(load_jsonl(root / "data/manifests/discovered_documents.jsonl"), [previous])

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
                raw.write_bytes(b"%PDF-1.7\nfixture PDF")
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
