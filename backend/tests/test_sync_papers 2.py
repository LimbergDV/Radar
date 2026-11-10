"""Tests del caso de uso de papers de Hugging Face.

Todo aquí es puro: mapeo de la API, deduplicación, frescura y ranking. No se
toca la red ni PostgreSQL, así que corre siempre.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.core.entities.config import PaperConfig
from src.core.use_cases import sync_papers as uc
from src.core.use_cases.update_source_config import validate_paper_config

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _entry(**overrides) -> dict:
    paper = {
        "id": "2610.36082",
        "title": "How Much Does the Hint Matter?",
        "summary": "Financial institutions ...",
        "publishedAt": "2026-10-26T00:00:00.000Z",
        "submittedOnDailyAt": "2026-10-28T00:00:00.000Z",
        "authors": [{"name": "Johnny Yu"}, {"name": "Cyril Gorlla"}],
        "upvotes": 12,
        "ai_summary": "Fin-SD improves local reasoning.",
        "ai_keywords": ["distillation", "reasoning"],
        "organization": {"name": "ctgt-inc", "fullname": "CTGT, Inc."},
        "githubRepo": "https://github.com/johnnyhyu/fin-sd",
        "projectPage": "https://example.com/project",
        "linkedModels": [{"id": "org/model"}],
        "linkedDatasets": [{"id": "org/dataset"}],
        "linkedSpaces": [{"id": "org/space"}],
    }
    paper.update(overrides)
    return {
        "paper": paper,
        "thumbnail": "https://cdn-thumbnails.huggingface.co/social-thumbnails/papers/x.png",
        "numComments": 3,
    }


class TestBuildPaper:
    def test_maps_nested_api_entry(self):
        paper = uc.build_paper(_entry(), synced_at=NOW)

        assert paper.id == "2610.36082"
        assert paper.title.startswith("How Much")
        assert paper.abstract.startswith("Financial")
        assert paper.ai_summary.startswith("Fin-SD")
        assert paper.submitted_on_daily_at == datetime(2026, 10, 28, tzinfo=timezone.utc)
        assert paper.authors == ["Johnny Yu", "Cyril Gorlla"]
        assert paper.organization == "CTGT, Inc."
        assert paper.upvotes == 12
        assert paper.comments == 3
        assert paper.source == "daily"

    def test_builds_urls_from_arxiv_id(self):
        paper = uc.build_paper(_entry(), synced_at=NOW)

        assert paper.hf_url == "https://huggingface.co/papers/2610.36082"
        assert paper.arxiv_url == "https://arxiv.org/abs/2610.36082"
        assert paper.pdf_url == "https://arxiv.org/pdf/2610.36082"

    def test_extracts_linked_resources(self):
        paper = uc.build_paper(_entry(), synced_at=NOW)

        assert paper.linked_models == ["org/model"]
        assert paper.linked_datasets == ["org/dataset"]
        assert paper.linked_spaces == ["org/space"]

    def test_accepts_flat_entry(self):
        """El mapeo no debe depender de la envoltura `paper` de la API."""
        flat = _entry()["paper"]
        paper = uc.build_paper(flat, synced_at=NOW)
        assert paper.id == "2610.36082"

    def test_rejects_entry_without_id(self):
        with pytest.raises(ValueError):
            uc.build_paper({"paper": {"title": "sin id"}})

    def test_missing_published_date_falls_back_to_sync_time(self):
        paper = uc.build_paper(
            _entry(publishedAt=None), synced_at=NOW
        )
        assert paper.published_at == NOW

    def test_handles_search_source(self):
        paper = uc.build_paper(_entry(), source="search", synced_at=NOW)
        assert paper.source == "search"


class TestDateParsing:
    def test_parses_z_suffix(self):
        assert uc.parse_datetime("2026-10-28T00:00:00.000Z") == datetime(
            2026, 10, 28, tzinfo=timezone.utc
        )

    def test_parses_date_only(self):
        assert uc.parse_datetime("2026-10-28") == datetime(
            2026, 10, 28, tzinfo=timezone.utc
        )

    def test_assumes_utc_for_naive_datetime(self):
        parsed = uc.parse_datetime(datetime(2026, 10, 28, 5))
        assert parsed is not None and parsed.tzinfo == timezone.utc

    def test_returns_fallback_on_garbage(self):
        assert uc.parse_datetime("ayer", fallback=NOW) == NOW
        assert uc.parse_datetime(None, fallback=NOW) == NOW


class TestDedupeAndFreshness:
    def test_dedupe_keeps_one_and_merges_fields(self):
        daily = uc.build_paper(_entry(), source="daily", synced_at=NOW)
        sparse = uc.build_paper(
            {
                "paper": {
                    "id": "2610.36082",
                    "title": "How Much Does the Hint Matter?",
                    "summary": "",
                    "publishedAt": "2026-10-26T00:00:00.000Z",
                    "upvotes": 20,
                    "linkedModels": [{"id": "org/other"}],
                }
            },
            source="search",
            synced_at=NOW,
        )

        merged = uc.dedupe([daily, sparse])

        assert len(merged) == 1
        assert merged[0].source == "daily"
        # El resumen bueno no se pierde porque la búsqueda viniera vacía.
        assert merged[0].abstract.startswith("Financial")
        assert merged[0].upvotes == 20
        assert set(merged[0].linked_models) == {"org/model", "org/other"}

    def test_within_days_uses_daily_date_not_arxiv_date(self):
        """Un paper viejo en arXiv puede entrar al Daily hoy: cuenta como fresco."""
        old_but_daily = uc.build_paper(
            _entry(publishedAt="2020-01-01T00:00:00Z"), synced_at=NOW
        )
        kept = uc.within_days([old_but_daily], 7, now=NOW)
        assert kept == [old_but_daily]

    def test_within_days_drops_stale_papers(self):
        stale = uc.build_paper(
            _entry(
                publishedAt=(NOW - timedelta(days=30)).isoformat(),
                submittedOnDailyAt=None,
            ),
            source="search",
            synced_at=NOW,
        )
        assert uc.within_days([stale], 7, now=NOW) == []

    def test_within_days_zero_disables_filter(self):
        stale = uc.build_paper(
            _entry(publishedAt="2020-01-01T00:00:00Z", submittedOnDailyAt=None),
            synced_at=NOW,
        )
        assert uc.within_days([stale], 0, now=NOW) == [stale]

    def test_rank_orders_by_upvotes_then_caps(self):
        low = uc.build_paper(_entry(id="a", upvotes=1), synced_at=NOW)
        high = uc.build_paper(_entry(id="b", upvotes=99), synced_at=NOW)
        assert [p.id for p in uc.rank([low, high], 1)] == ["b"]
        assert [p.id for p in uc.rank([low, high], 10)] == ["b", "a"]


class TestConfig:
    def test_search_terms_use_defaults_when_empty(self):
        assert uc.build_search_terms(PaperConfig(keywords=[])) == [
            "agents",
            "reasoning",
            "llm",
        ]

    def test_search_terms_are_cleaned_and_deduped(self):
        config = PaperConfig(keywords=[" agents ", "AGENTS", "", "vision"])
        assert uc.build_search_terms(config) == ["agents", "vision"]

    def test_validate_clamps_and_keeps_at_least_daily(self):
        config = validate_paper_config(
            PaperConfig(
                keywords=[],
                max_results=999,
                days_back=0,
                include_daily=False,
                include_search=False,
            )
        )
        assert config.max_results == 100
        assert config.days_back == 1
        assert config.include_daily is True
        assert config.keywords == ["agents", "reasoning", "llm"]
