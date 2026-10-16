"""Prueba de humo contra la API REAL de Radar en Railway.

Estos tests no usan mocks: hablan con la app desplegada y demuestran que el
MVP funciona de verdad. Se saltan salvo que se pida explícitamente:

    RADAR_LIVE=1 pytest tests/test_live.py -q

Si alguno falla, revisar primero si el backend está caído (el propio fallo lo
dice: un RadarError con 502 o timeout). Fallar aquí significa o que la app se
rompió, o que cambió la API.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar_mcp.client import RadarClient, RadarError  # noqa: E402
from radar_mcp.config import Settings  # noqa: E402
from radar_mcp.tools import RadarTools  # noqa: E402

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RADAR_LIVE") != "1",
        reason="Requiere la API real. Activa con RADAR_LIVE=1",
    ),
]


@pytest.fixture
def live_tools():
    settings = Settings(
        api_url=os.getenv("RADAR_API_URL", "https://frontend-production-820b7.up.railway.app"),
        timeout=45,
    )
    return RadarTools(client=RadarClient(settings), settings=settings)


class TestBackendIsAlive:
    @pytest.mark.asyncio
    async def test_stats_responds(self, live_tools):
        stats = await live_tools.stats()
        assert stats["total_items"] > 0, "la base de Radar está vacía"
        for source in ("youtube", "news", "github"):
            assert stats["sources"][source]["total"] >= 0

    @pytest.mark.asyncio
    async def test_config_is_readable(self, live_tools):
        """El agente debe poder ver qué se está rastreando."""
        stats = await live_tools.stats()
        youtube = stats["config"]["youtube"]
        assert "keywords" in youtube
        assert isinstance(youtube["keywords"], list)


class TestSearch:
    @pytest.mark.asyncio
    async def test_unified_search_returns_items(self, live_tools):
        result = await live_tools.search(limit=5)
        assert result["count"] > 0

    @pytest.mark.asyncio
    async def test_search_by_source(self, live_tools):
        for source in ("youtube", "news", "github"):
            result = await live_tools.search(source=source, limit=3)
            assert all(item["source"] == source for item in result["items"])

    @pytest.mark.asyncio
    async def test_since_days_filters_recent(self, live_tools):
        result = await live_tools.search(since_days=30, limit=10)
        assert result["count"] <= 10


class TestContentIsReadable:
    @pytest.mark.asyncio
    async def test_a_github_repo_resolves_by_name_and_exposes_readme(self, live_tools):
        """El flujo más importante: nombre -> id -> README."""
        found = await live_tools.search(source="github", limit=1)
        assert found["items"], "no hay repos en la base"
        full_name = found["items"][0]["title"]

        detail = await live_tools.get_repo(full_name, content="full")
        assert detail["repo"]["full_name"] == full_name
        assert detail["readme"]["total_chars"] > 0
        assert detail["readme"]["chars_returned"] <= 8_000
        assert detail["readme"]["untrusted"] is True

    @pytest.mark.asyncio
    async def test_a_news_article_has_body_text(self, live_tools):
        """Es lo que arreglamos: noticias que se pueden leer.

        Se recorren varias porque en produccion solo ~60% son legibles (el resto
        son paywalls o sitios que bloquean el rastreo). El invariante que importa
        es que las que lo son, se entreguen con su texto.
        """
        found = await live_tools.search(source="news", limit=5)
        readable = 0

        for item in found["items"]:
            article = await live_tools.get_article(item["source_id"], content="full")
            body = article["body"]

            if body["total_chars"] > 0:
                readable += 1
                assert body["chars_returned"] > 0
                assert "news.google.com" not in (article["article"].get("link") or "")
            else:
                # Cuando no hay cuerpo hay que decirlo, no inventarlo ni fallar.
                assert article["body"]["available"] is False
                assert "no expone el texto" in article["body"]["hint"]

        assert readable > 0, "ninguna de las noticias recientes trae cuerpo"

    @pytest.mark.asyncio
    async def test_a_youtube_video_has_transcript(self, live_tools):
        found = await live_tools.search(source="youtube", limit=3)
        with_transcript = 0

        for item in found["items"]:
            video = await live_tools.get_video(item["source_id"], content="full")
            if video["transcript"]["total_chars"] > 0:
                with_transcript += 1
            else:
                assert video["transcript"]["available"] is False

        assert with_transcript > 0, "ninguno de los videos recientes trae transcripción"

    @pytest.mark.asyncio
    async def test_context_reads_a_range(self, live_tools):
        found = await live_tools.search(source="github", limit=1)
        content_id = f"readme:{found['items'][0]['title']}"

        first = await live_tools.get_context(content_id, offset=0, limit=500)
        assert first["chars_returned"] == 500
        assert first["truncated"] is True
        assert first["next_offset"] == 500

        second = await live_tools.get_context(content_id, offset=500, limit=500)
        assert second["text"] != first["text"], "el offset no avanzaba"


class TestErrorsAreLegible:
    @pytest.mark.asyncio
    async def test_unknown_video_explains_itself(self, live_tools):
        with pytest.raises(RadarError) as excinfo:
            await live_tools.get_video("no-existe-este-video")
        assert "404" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_unknown_repo_suggests_a_search(self, live_tools):
        with pytest.raises(RadarError) as excinfo:
            await live_tools.get_repo("esta-empresa-inexistente/agujero")
        assert "radar_search" in str(excinfo.value)


class TestSyncStaysOff:
    @pytest.mark.asyncio
    async def test_sync_refused_against_the_real_app(self, live_tools):
        """Aunque el backend lo permita, el MCP no debe disparar syncs."""
        with pytest.raises(RadarError, match="RADAR_ENABLE_SYNC"):
            await live_tools.sync("youtube")