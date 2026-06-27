from __future__ import annotations

from datetime import datetime

from .models import SeedRequest, SourceDefinition

CURRENT_YEAR = datetime.now().year


SPBAO_OFFICIAL_SEED_CONTEXTS = {
    # XXVII (2020)
    "http://school.astro.spbu.ru/?q=node/596": {
        "year": 2020,
        "stage_or_round": "final",
        "round_detail": "practical",
    },
    # XXVIII (2021)
    "http://school.astro.spbu.ru/?q=node/604": {
        "year": 2021,
        "stage_or_round": "regional",
    },
    "http://school.astro.spbu.ru/?q=node/620": {
        "year": 2021,
        "stage_or_round": "qualifying",
    },
    "http://school.astro.spbu.ru/?q=node/622": {
        "year": 2021,
        "stage_or_round": "final",
        "round_detail": "theoretical",
    },
    "http://school.astro.spbu.ru/?q=node/624": {
        "year": 2021,
        "stage_or_round": "final",
        "round_detail": "practical",
    },
    # XXIX (2022)
    "http://school.astro.spbu.ru/?q=node/630": {
        "year": 2022,
        "stage_or_round": "regional",
    },
    "http://school.astro.spbu.ru/?q=node/640": {
        "year": 2022,
        "stage_or_round": "qualifying",
    },
    "http://school.astro.spbu.ru/?q=node/642": {
        "year": 2022,
        "stage_or_round": "final",
        "round_detail": "theoretical",
    },
    "http://school.astro.spbu.ru/?q=node/646": {
        "year": 2022,
        "stage_or_round": "final",
        "round_detail": "practical",
    },
    # XXX (2023)
    "http://school.astro.spbu.ru/?q=node/649": {
        "year": 2023,
        "stage_or_round": "regional",
    },
    "http://school.astro.spbu.ru/?q=node/652": {
        "year": 2023,
        "stage_or_round": "qualifying",
    },
    "http://school.astro.spbu.ru/?q=node/654": {
        "year": 2023,
        "stage_or_round": "final",
        "round_detail": "theoretical",
    },
    "http://school.astro.spbu.ru/?q=node/656": {
        "year": 2023,
        "stage_or_round": "final",
        "round_detail": "practical",
    },
    # XXXI (2024)
    "http://school.astro.spbu.ru/?q=node/663": {
        "year": 2024,
        "stage_or_round": "qualifying",
    },
    "http://school.astro.spbu.ru/?q=node/665": {
        "year": 2024,
        "stage_or_round": "final",
        "round_detail": "theoretical",
    },
    "http://school.astro.spbu.ru/?q=node/667": {
        "year": 2024,
        "stage_or_round": "final",
        "round_detail": "practical",
    },
    # XXXII (2025)
    "http://school.astro.spbu.ru/?q=node/673": {
        "year": 2025,
        "stage_or_round": "qualifying",
    },
    "http://school.astro.spbu.ru/?q=node/678": {
        "year": 2025,
        "stage_or_round": "final",
        "round_detail": "theoretical",
    },
    "http://school.astro.spbu.ru/?q=node/680": {
        "year": 2025,
        "stage_or_round": "final",
        "round_detail": "practical",
    },
    # XXXIII (2026)
    "http://school.astro.spbu.ru/?q=node/685": {
        "year": 2026,
        "stage_or_round": "qualifying",
    },
    "http://school.astro.spbu.ru/?q=node/687": {
        "year": 2026,
        "stage_or_round": "final",
        "round_detail": "theoretical",
    },
}

SOURCE_DEFINITIONS: list[SourceDefinition] = [
    SourceDefinition(
        source_id="vsosh_edsoo_official",
        label="ВсОШ астрономия: официальный раздел vserosolimp.edsoo.ru",
        olympiad_family="vsosh_astronomy",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://vserosolimp.edsoo.ru/astronom"],
        notes="Официальные требования и архивы последних лет.",
    ),
    SourceDefinition(
        source_id="vsosh_edsoo_stage_documents",
        label="ВсОШ астрономия: официальные страницы этапов vserosolimp.edsoo.ru",
        olympiad_family="vsosh_astronomy",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=[
            "https://vserosolimp.edsoo.ru/region_way",
            "https://vserosolimp.edsoo.ru/zakluchit_way",
        ],
        notes="Официальные требования, регламенты и приказы регионального и заключительного этапов.",
        extras={
            "default_context": {"record_seed_page": False, "year": CURRENT_YEAR},
            "seed_contexts": {
                "https://vserosolimp.edsoo.ru/region_way": {"stage_or_round": "regional"},
                "https://vserosolimp.edsoo.ru/zakluchit_way": {"stage_or_round": "final"},
            },
        },
    ),
    SourceDefinition(
        source_id="vsosh_moscow_year_pages",
        label="ВсОШ астрономия: годовые страницы на vos.olimpiada.ru",
        olympiad_family="vsosh_astronomy",
        source_role="mirror",
        source_priority=2,
        strategy="vsosh_year_pages",
        notes="Глубокий архив по учебным годам, включая регион и заключительный этапы.",
        extras={"year_start": 2010, "year_end": CURRENT_YEAR},
    ),
    SourceDefinition(
        source_id="vsosh_astroedu_archive",
        label="ВсОШ астрономия: архив задач и решений на astroedu.ru",
        olympiad_family="vsosh_astronomy",
        source_role="archive",
        source_priority=3,
        strategy="static",
        seed_urls=["https://astroedu.ru/vos/problems"],
        notes="Глубокий архив задач и решений ВсОШ (1994–наст. время), регион и заключительный этапы.",
        extras={"default_context": {"record_seed_page": False}},
    ),
    SourceDefinition(
        source_id="vsosh_moscow_team_year",
        label="ВсОШ астрономия: страница команды Москвы",
        olympiad_family="vsosh_astronomy",
        source_role="mirror",
        source_priority=3,
        strategy="static",
        seed_urls=[f"https://vos.olimpiada.ru/team/year/{CURRENT_YEAR}"],
        notes="Публичная страница с provenance-ссылками на заключительный этап и результаты команды Москвы.",
        extras={
            "default_context": {
                "year": CURRENT_YEAR,
                "stage_or_round": "final",
                "document_type": "info",
            }
        },
    ),
    SourceDefinition(
        source_id="vsosh_sirius_final",
        label="ВсОШ астрономия: официальный сайт заключительного этапа в Сириусе",
        olympiad_family="vsosh_astronomy",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://astro.siriusolymp.ru/results"],
        notes="Официальные результаты заключительного этапа и ссылка на протокол жюри.",
        extras={
            "default_context": {
                "year": CURRENT_YEAR,
                "stage_or_round": "final",
            }
        },
    ),
    SourceDefinition(
        source_id="struve_moscow_year_pages",
        label="Струве: годовые страницы на vos.olimpiada.ru",
        olympiad_family="struve",
        source_role="mirror",
        source_priority=2,
        strategy="vsosh_year_pages",
        notes="Материалы олимпиады Струве на годовых страницах архива vos.olimpiada.ru.",
        extras={"year_start": 2022, "year_end": CURRENT_YEAR},
    ),
    SourceDefinition(
        source_id="owao_tasks_official",
        label="OWAO: official archive page with tasks and solutions",
        olympiad_family="owao",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://owao.siriusolymp.ru/tasks"],
        notes="Официальная страница архива OWAO с материалами прошлых лет.",
        extras={"default_context": {"record_seed_page": False}},
    ),
    SourceDefinition(
        source_id="serbia_astronomy_official",
        label="Serbia astronomy: official NAOK archive page",
        olympiad_family="serbia_astronomy",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://www.das.org.rs/naoc.html"],
        notes="Официальная страница NAOK / DAS с архивом задач и решений по годам.",
    ),
    SourceDefinition(
        source_id="russia_team_qual_archive",
        label="Russia team qualification: archive of qualifying tests",
        olympiad_family="russia_team_qual",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://astroedu.ru/hq/problems/"],
        notes="Архив квалификационных тестов для кандидатов в сборную России по астрономии и астрофизике.",
        extras={"default_context": {"record_seed_page": False}},
    ),
    SourceDefinition(
        source_id="mao_moscow_archive",
        label="МАО: архив на mos.olimpiada.ru",
        olympiad_family="mao",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://mos.olimpiada.ru/tasks/astr"],
        notes="Официальный архив задач и решений МАО.",
    ),
    SourceDefinition(
        source_id="spbao_official",
        label="СПбАО: официальный сайт school.astro.spbu.ru",
        olympiad_family="spbao",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=[
            # XXVII (2020)
            "http://school.astro.spbu.ru/?q=node/596",
            # XXVIII (2021)
            "http://school.astro.spbu.ru/?q=node/604",
            "http://school.astro.spbu.ru/?q=node/620",
            "http://school.astro.spbu.ru/?q=node/622",
            "http://school.astro.spbu.ru/?q=node/624",
            # XXIX (2022)
            "http://school.astro.spbu.ru/?q=node/630",
            "http://school.astro.spbu.ru/?q=node/640",
            "http://school.astro.spbu.ru/?q=node/642",
            "http://school.astro.spbu.ru/?q=node/646",
            # XXX (2023)
            "http://school.astro.spbu.ru/?q=node/649",
            "http://school.astro.spbu.ru/?q=node/652",
            "http://school.astro.spbu.ru/?q=node/654",
            "http://school.astro.spbu.ru/?q=node/656",
            # XXXI (2024)
            "http://school.astro.spbu.ru/?q=node/663",
            "http://school.astro.spbu.ru/?q=node/665",
            "http://school.astro.spbu.ru/?q=node/667",
            # XXXII (2025)
            "http://school.astro.spbu.ru/?q=node/673",
            "http://school.astro.spbu.ru/?q=node/678",
            "http://school.astro.spbu.ru/?q=node/680",
            # XXXIII (2026)
            "http://school.astro.spbu.ru/?q=node/685",
            "http://school.astro.spbu.ru/?q=node/687",
        ],
        notes="Официальный архив СПбАО на сайте кафедры астрономии СПбГУ (2020–2026, все туры с PDF).",
        extras={
            "default_context": {"record_seed_page": False},
            "seed_contexts": SPBAO_OFFICIAL_SEED_CONTEXTS,
        },
    ),
    SourceDefinition(
        source_id="spbao_olimpiada_archive",
        label="СПбАО: архив на olimpiada.ru",
        olympiad_family="spbao",
        source_role="archive",
        source_priority=2,
        strategy="static",
        seed_urls=["https://olimpiada.ru/activity/287/tasks"],
        notes="Архив с навигацией по годам и классам.",
    ),
    SourceDefinition(
        source_id="spbao_year_class_pages",
        label="СПбАО: годовые страницы на olimpiada.ru",
        olympiad_family="spbao",
        source_role="archive",
        source_priority=2,
        strategy="spbao_year_class_pages",
        notes="Глубокие страницы архива по годам и классам.",
        extras={
            "year_start": 2010,
            "year_end": CURRENT_YEAR,
            "classes": list(range(5, 12)),
            "default_context": {"record_seed_page": False, "container_only": True},
        },
    ),
    SourceDefinition(
        source_id="ioaa_problems",
        label="IOAA: problems from past IOAA",
        olympiad_family="ioaa",
        source_role="official",
        source_priority=1,
        strategy="static",
        seed_urls=["https://www.ioaastrophysics.org/resources/problems-from-past-ioaa"],
        notes="Официальная подборка задач, решений и marking schemes.",
        extras={"default_context": {"record_seed_page": False}},
    ),
    SourceDefinition(
        source_id="ioaa_proceedings",
        label="IOAA: past proceedings",
        olympiad_family="ioaa",
        source_role="official",
        source_priority=2,
        strategy="static",
        seed_urls=["https://www.ioaastrophysics.org/resources/past-proceedings"],
        notes="Официальные proceedings с дополнительными материалами.",
        extras={"default_context": {"record_seed_page": False}},
    ),
    SourceDefinition(
        source_id="ioaa_past_olympiads",
        label="IOAA: past olympiads index",
        olympiad_family="ioaa",
        source_role="official",
        source_priority=2,
        strategy="static",
        seed_urls=["https://www.ioaastrophysics.org/past-olympiads"],
        notes="Официальный индекс прошлых олимпиад с годовыми страницами.",
        extras={"default_context": {"record_seed_page": False}},
    ),
    SourceDefinition(
        source_id="iao_eaae_index",
        label="IAO: индекс EAAE со ссылками на годы",
        olympiad_family="iao",
        source_role="archive",
        source_priority=2,
        strategy="static",
        seed_urls=["https://eaae-astronomy.org/news/international-astronomy-olympiad"],
        notes="Исторический обзор со ссылками на официальные страницы IAO.",
        extras={
            "default_context": {
                "record_seed_page": False,
                "follow_second_hop": True,
                "max_follow_depth": 2,
            }
        },
    ),
    SourceDefinition(
        source_id="iao_astroarena_mirror",
        label="IAO: mirror Astroarena",
        olympiad_family="iao",
        source_role="mirror",
        source_priority=2,
        strategy="static",
        seed_urls=["https://astroarena.github.io/astroarena/olympiads/iao.html"],
        notes="Подробный mirror с PDF по годам и турам.",
    ),
    SourceDefinition(
        source_id="iao_fizmat_mirror",
        label="IAO: mirror Fizmat",
        olympiad_family="iao",
        source_role="mirror",
        source_priority=3,
        strategy="static",
        seed_urls=["https://fizmat.space/international/"],
        notes="Дополнительный mirror с отдельными PDF и ZIP.",
    ),
]


def _seed_context_for_url(source: SourceDefinition, url: str, extra_context: dict | None = None) -> dict:
    context = dict(source.extras.get("default_context", {}))
    context.update(source.extras.get("seed_contexts", {}).get(url, {}))
    if extra_context:
        context.update(extra_context)
    return context


def iter_seed_requests(source: SourceDefinition) -> list[SeedRequest]:
    if source.strategy == "static":
        return [
            SeedRequest(
                source_id=source.source_id,
                url=url,
                olympiad_family=source.olympiad_family,
                source_role=source.source_role,
                source_priority=source.source_priority,
                context=_seed_context_for_url(source, url),
            )
            for url in source.seed_urls
        ]

    if source.strategy == "vsosh_year_pages":
        seed_requests: list[SeedRequest] = []
        year_start = int(source.extras["year_start"])
        year_end = int(source.extras["year_end"])
        for end_year in range(year_start, year_end + 1):
            season_start = end_year - 1
            seed_requests.append(
                SeedRequest(
                    source_id=source.source_id,
                    url=f"https://vos.olimpiada.ru/astr/{season_start}_{end_year}",
                    olympiad_family=source.olympiad_family,
                    source_role=source.source_role,
                    source_priority=source.source_priority,
                    context=_seed_context_for_url(
                        source,
                        f"https://vos.olimpiada.ru/astr/{season_start}_{end_year}",
                        {"season_start": season_start, "season_end": end_year},
                    ),
                )
            )
        return seed_requests

    if source.strategy == "spbao_year_class_pages":
        seed_requests = []
        year_start = int(source.extras["year_start"])
        year_end = int(source.extras["year_end"])
        classes = list(source.extras["classes"])
        for year in range(year_start, year_end + 1):
            for grade in classes:
                seed_requests.append(
                    SeedRequest(
                        source_id=source.source_id,
                        url=f"https://olimpiada.ru/activity/287/tasks/{year}?class={grade}&year={year}",
                        olympiad_family=source.olympiad_family,
                        source_role=source.source_role,
                        source_priority=source.source_priority,
                        context=_seed_context_for_url(
                            source,
                            f"https://olimpiada.ru/activity/287/tasks/{year}?class={grade}&year={year}",
                            {"archive_year": year, "grade": grade},
                        ),
                    )
                )
        return seed_requests

    raise ValueError(f"Unsupported seed strategy: {source.strategy}")
