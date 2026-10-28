"""Tests del servidor MCP de Radar.

Dos tipos:
- `Test*` usan httpx.MockTransport: rapidísimos, sin red, deterministas.
- Los marcados con `@pytest.mark.live` pegan a la API real; se saltan salvo
  que se ejecuten con `RADAR_LIVE=1`. Son los que demuestran que el MVP
  funciona contra la app desplegada.

    RADAR_LIVE=1 pytest tests/ -q -m live
"""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar_mcp.client import RadarClient, RadarError, _extract_detail  # noqa: E402
from radar_mcp.config import Settings, load_settings  # noqa: E402
from radar_mcp.server import build_server  # noqa: E402
from radar_mcp.tools import (  # noqa: E402
    RadarTools,
    clip,
    keep_since_days,
    matches_repo_name,
    parse_content_id,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def make_tools(handler, **settings_kwargs) -> RadarTools:
    """Construye las herramientas con un transporte HTTP simulado.

    Hay que envolver el handler en httpx.MockTransport: si se pasa la función
    suelta, httpx no sabe qué hacer con ella y revienta al abrir el cliente.
    """
    settings = Settings(api_url="https://radar.test", **settings_kwargs)
    transport = httpx.MockTransport(handler)
    return RadarTools(client=RadarClient(settings, transport=transport), settings=settings)


def json_response(payload, status_code=200):
    return httpx.Response(status_code, json=payload)


def make_client(handler, **settings_kwargs) -> RadarClient:
    """Cliente con transporte simulado (httpx exige el wrapper, no la función)."""
    return RadarClient(
        Settings(api_url="https://radar.test", **settings_kwargs),
        transport=httpx.MockTransport(handler),
    )


# ─────────────────────────── lógica pura ───────────────────────────


class TestClip:
    def test_returns_everything_when_it_fits(self):
        block = clip("hola mundo", content_id="article:1", budget=1000)
        assert block["chars_returned"] == 10
        assert block["truncated"] is False
        assert block["next_offset"] is None

    def test_declares_truncation_and_next_offset(self):
        block = clip("abcdefghij", content_id="article:1", budget=4)
        assert block["chars_returned"] == 4
        assert block["total_chars"] == 10
        assert block["truncated"] is True
        assert block["next_offset"] == 4
        assert block["text"] == "abcd"

    def test_reads_a_window_with_offset(self):
        block = clip("abcdefghij", content_id="readme:x", budget=3, offset=4)
        assert block["text"] == "efg"
        assert block["offset"] == 4

    def test_handles_none_content(self):
        block = clip(None, content_id="transcript:v1", budget=100)
        assert block["total_chars"] == 0
        assert block["text"] == ""
        assert block["truncated"] is False

    def test_content_is_always_flagged_untrusted(self):
        """Un README puede intentar dar ordenes al agente: se marca siempre."""
        assert clip("x", content_id="readme:r", budget=10)["untrusted"] is True

    def test_available_is_present_both_with_and_without_content(self):
        """El agente ramifica sobre `available`; si solo aparece a veces, falla."""
        assert clip("texto", content_id="a:1", budget=10)["available"] is True
        assert clip("", content_id="a:1", budget=10)["available"] is False
        assert clip(None, content_id="a:1", budget=10)["available"] is False

    def test_negative_offset_is_clamped(self):
        assert clip("abc", content_id="a:1", budget=2, offset=-5)["offset"] == 0


class TestKeepSinceDays:
    def test_keeps_recent_only(self):
        items = [
            {"published_at": "2099-01-01T00:00:00+00:00"},
            {"published_at": "2000-01-01T00:00:00+00:00"},
        ]
        assert keep_since_days(items, 7) == [items[0]]

    def test_no_filter_returns_everything(self):
        items = [{"published_at": "2000-01-01T00:00:00+00:00"}]
        assert keep_since_days(items, None) == items

    def test_drops_unparseable_dates(self):
        assert keep_since_days([{"published_at": "ayer"}], 7) == []
        assert keep_since_days([{"title": "sin fecha"}], 7) == []


class TestRepoNameMatching:
    @pytest.mark.parametrize(
        ("candidate", "wanted", "expected"),
        [
            ("facebook/react", "facebook/react", True),
            ("Facebook/React", "facebook/react", True),
            ("NousResearch/hermes-agent", "hermes-agent", True),
            ("facebook/react-native", "react", False),
            ("otro/react", "react", True),
            ("", "react", False),
            ("react", "", False),
        ],
    )
    def test_matching(self, candidate, wanted, expected):
        assert matches_repo_name(candidate, wanted) is expected


class TestParseContentId:
    def test_parses_known_kinds(self):
        assert parse_content_id("readme:facebook/react") == ("readme", "facebook/react")
        assert parse_content_id("transcript:abc123") == ("transcript", "abc123")
        assert parse_content_id("paper:2610.36082") == ("paper", "2610.36082")
        assert parse_content_id("paper_ai:2610.36082") == ("paper_ai", "2610.36082")

    def test_rejects_missing_ref(self):
        with pytest.raises(RadarError, match="content_id inválido"):
            parse_content_id("readme")


# ─────────────────────────── cliente ───────────────────────────


class TestClient:
    @pytest.mark.asyncio
    async def test_returns_json_on_success(self):
        async def handler(request):
            return json_response({"ok": True})

        client = make_client(handler)
        assert await client.get_json("/api/feed/stats") == {"ok": True}

    @pytest.mark.asyncio
    async def test_sends_api_key_when_configured(self):
        seen = {}

        async def handler(request):
            seen["key"] = request.headers.get("X-API-Key")
            return json_response({})

        client = make_client(handler, api_key="secreto")
        await client.get_json("/api/feed/stats")
        assert seen["key"] == "secreto"

    @pytest.mark.asyncio
    async def test_omits_api_key_when_absent(self):
        seen = {}

        async def handler(request):
            seen["key"] = request.headers.get("X-API-Key")
            return json_response({})

        client = make_client(handler)
        await client.get_json("/api/feed/stats")
        assert seen["key"] is None

    @pytest.mark.asyncio
    async def test_fastapi_detail_becomes_legible_message(self):
        async def handler(request):
            return json_response({"detail": "YouTube no tiene nada que buscar"}, status_code=502)

        client = make_client(handler)
        with pytest.raises(RadarError) as excinfo:
            await client.get_json("/api/youtube/sync")
        assert "no tiene nada que buscar" in str(excinfo.value)
        assert excinfo.value.status == 502

    @pytest.mark.asyncio
    async def test_401_explains_the_api_key(self):
        async def handler(request):
            return json_response({"detail": "Not authenticated"}, status_code=401)

        client = make_client(handler)
        with pytest.raises(RadarError, match="RADAR_API_KEY"):
            await client.get_json("/api/feed/stats")

    @pytest.mark.asyncio
    async def test_validation_error_names_the_field(self):
        async def handler(request):
            return json_response(
                {"detail": [{"loc": ["query", "limit"], "msg": "too big"}]}, status_code=422
            )

        client = make_client(handler)
        # `loc[0]` es el origen ("query"), no el campo: se omite a propósito.
        with pytest.raises(RadarError, match="limit: too big"):
            await client.get_json("/api/feed")

    @pytest.mark.asyncio
    async def test_html_error_from_proxy_does_not_leak(self):
        """Railway puede devolver HTML; no debe acabar en el mensaje del agente."""


        async def handler(request):
            return httpx.Response(502, text="<html>502 Bad Gateway</html>")

        client = make_client(handler)
        with pytest.raises(RadarError) as excinfo:
            await client.get_json("/api/feed/stats")
        assert "<html>" not in str(excinfo.value)
        assert "backend no pudo" in str(excinfo.value).lower()

    def test_extract_detail_ignores_html(self):


        response = httpx.Response(500, text="<html>oops</html>")
        assert _extract_detail(response) is None


# ─────────────────────────── herramientas ───────────────────────────


FEED = {
    "total": 2,
    "has_more": False,
    "items": [
        {
            "source": "github",
            "source_id": "42",
            "title": "facebook/react",
            "published_at": "2099-01-01T00:00:00+00:00",
        },
        {
            "source": "news",
            "source_id": "7",
            "title": "OTRO",
            "published_at": "2099-01-01T00:00:00+00:00",
        },
    ],
}


class TestSearch:
    @pytest.mark.asyncio
    async def test_rejects_unknown_source(self):
        tools = make_tools(lambda r: json_response({}))
        with pytest.raises(RadarError, match="source inválida"):
            await tools.search(source="tiktok")

    @pytest.mark.asyncio
    async def test_warns_about_the_weak_search(self):
        async def handler(request):
            return json_response(FEED)

        tools = make_tools(handler)
        result = await tools.search(query="react")
        assert result["count"] == 2
        assert any("subcadena" in note for note in result["notes"])

    @pytest.mark.asyncio
    async def test_since_days_is_applied_and_declared(self):
        async def handler(request):
            return json_response(
                {
                    **FEED,
                    "items": [
                        {"published_at": "2000-01-01T00:00:00+00:00"},
                        {"published_at": "2099-01-01T00:00:00+00:00"},
                    ],
                }
            )

        tools = make_tools(handler)
        result = await tools.search(since_days=1)
        assert result["count"] == 1
        assert any("en cliente" in note for note in result["notes"])


class TestGetVideo:
    @pytest.mark.asyncio
    async def test_summary_does_not_return_the_transcript(self):
        async def handler(request):
            return json_response({"id": "v1", "title": "T", "transcript": "x" * 4000})

        tools = make_tools(handler)
        result = await tools.get_video("v1")

        assert "transcript" not in result["video"]
        assert result["transcript"]["available"] is True
        assert result["transcript"]["total_chars"] == 4000
        assert result["transcript"]["content_id"] == "transcript:v1"
        assert "content='full'" in result["transcript"]["hint"]

    @pytest.mark.asyncio
    async def test_full_respects_the_budget(self):
        async def handler(request):
            return json_response({"id": "v1", "title": "T", "transcript": "y" * 5000})

        tools = make_tools(handler, max_content_chars=100)
        result = await tools.get_video("v1", content="full")

        assert result["transcript"]["chars_returned"] == 100
        assert result["transcript"]["total_chars"] == 5000
        assert result["transcript"]["truncated"] is True

    @pytest.mark.asyncio
    async def test_missing_transcript_is_said_plainly(self):
        async def handler(request):
            return json_response({"id": "v1", "title": "T", "transcript": ""})

        tools = make_tools(handler)
        result = await tools.get_video("v1")
        assert result["transcript"]["available"] is False
        assert "no tiene transcripción" in result["transcript"]["hint"]

    @pytest.mark.asyncio
    async def test_requires_video_id(self):
        tools = make_tools(lambda r: json_response({}))
        with pytest.raises(RadarError, match="Falta video_id"):
            await tools.get_video("")


class TestGetRepo:
    @pytest.mark.asyncio
    async def test_numeric_id_is_used_directly(self):
        seen = {}

        async def handler(request):
            seen["path"] = request.url.path
            return json_response({"full_name": "a/b", "readme": "r" * 100})

        tools = make_tools(handler)
        await tools.get_repo("123")
        assert seen["path"] == "/api/github/repos/123"

    @pytest.mark.asyncio
    async def test_name_is_resolved_to_an_id(self):
        paths = []

        async def handler(request):
            paths.append(request.url.path)
            if request.url.path == "/api/feed":
                return json_response(FEED)
            return json_response({"full_name": "facebook/react", "readme": "r" * 10})

        tools = make_tools(handler)
        result = await tools.get_repo("facebook/react")

        assert paths == ["/api/feed", "/api/github/repos/42"]
        assert result["resolved_from"] == "facebook/react"

    @pytest.mark.asyncio
    async def test_ambiguous_name_is_refused(self):
        """Devolver el repo equivocado es peor que fallar."""
        async def handler(request):
            return json_response(
                {
                    "items": [
                        {"title": "facebook/react-native", "source_id": "1"},
                        {"title": "facebook/react", "source_id": "2"},
                    ]
                }
            )

        tools = make_tools(handler)
        result = await tools.get_repo("react")
        assert result["resolved_from"] == "react"

        with pytest.raises(RadarError, match="react-native"):
            await tools.get_repo("otro/nada")

    @pytest.mark.asyncio
    async def test_unknown_repo_suggests_searching(self):
        async def handler(request):
            return json_response({"items": []})

        tools = make_tools(handler)
        with pytest.raises(RadarError, match="radar_search"):
            await tools.get_repo("no/existe")


class TestGetPaper:
    @pytest.mark.asyncio
    async def test_summary_does_not_return_the_texts(self):
        async def handler(request):
            return json_response(
                {
                    "id": "2610.36082",
                    "title": "Paper",
                    "abstract": "a" * 2500,
                    "ai_summary": "s" * 900,
                    "authors": ["A"],
                }
            )

        tools = make_tools(handler)
        result = await tools.get_paper("2610.36082")

        assert "abstract" not in result["paper"]
        assert "ai_summary" not in result["paper"]
        assert result["abstract"]["content_id"] == "paper:2610.36082"
        assert result["ai_summary"]["content_id"] == "paper_ai:2610.36082"
        assert result["abstract"]["available"] is True
        assert result["abstract"]["total_chars"] == 2500

    @pytest.mark.asyncio
    async def test_full_returns_and_clips_both_texts(self):
        async def handler(request):
            return json_response(
                {
                    "id": "p1",
                    "abstract": "a" * 300,
                    "ai_summary": "s" * 200,
                }
            )

        tools = make_tools(handler, max_content_chars=100)
        result = await tools.get_paper("p1", content="full")

        assert result["abstract"]["chars_returned"] == 100
        assert result["abstract"]["truncated"] is True
        assert result["abstract"]["next_offset"] == 100
        assert result["ai_summary"]["chars_returned"] == 100
        assert result["ai_summary"]["truncated"] is True

    @pytest.mark.asyncio
    async def test_missing_ai_summary_is_said_plainly(self):
        async def handler(request):
            return json_response({"id": "p1", "abstract": "texto", "ai_summary": ""})

        tools = make_tools(handler)
        result = await tools.get_paper("p1")
        assert result["ai_summary"]["available"] is False
        assert "no generó un AI summary" in result["ai_summary"]["hint"]

    @pytest.mark.asyncio
    async def test_requires_paper_id(self):
        tools = make_tools(lambda r: json_response({}))
        with pytest.raises(RadarError, match="Falta paper_id"):
            await tools.get_paper("")


class TestGetContext:
    @pytest.mark.asyncio
    async def test_reads_a_range_of_a_long_readme(self):
        async def handler(request):
            return json_response({"full_name": "a/b", "readme": "0123456789" * 10})

        tools = make_tools(handler)
        block = await tools.get_context("readme:7", offset=10, limit=5)

        assert block["text"] == "01234"
        assert block["offset"] == 10
        assert block["total_chars"] == 100

    @pytest.mark.asyncio
    async def test_reads_the_abstract_or_ai_summary_of_a_paper(self):
        async def handler(request):
            assert request.url.path == "/api/papers/2610.36082"
            return json_response(
                {"abstract": "abstract-text", "ai_summary": "ai-summary-text"}
            )

        tools = make_tools(handler)
        abstract = await tools.get_context("paper:2610.36082")
        ai = await tools.get_context("paper_ai:2610.36082")

        assert abstract["text"] == "abstract-text"
        assert ai["text"] == "ai-summary-text"

    @pytest.mark.asyncio
    async def test_rejects_unknown_kind(self):
        tools = make_tools(lambda r: json_response({}))
        with pytest.raises(RadarError, match="desconocido"):
            await tools.get_context("podcast:1")


class TestSyncIsGated:
    @pytest.mark.asyncio
    async def test_refused_by_default(self):
        tools = make_tools(lambda r: json_response({}), enable_sync=False)
        with pytest.raises(RadarError, match="RADAR_ENABLE_SYNC=1"):
            await tools.sync("youtube")

    @pytest.mark.asyncio
    async def test_works_when_enabled(self):
        async def handler(request):
            return json_response({"status": "success", "items_synced": 3})

        tools = make_tools(handler, enable_sync=True)
        assert (await tools.sync("youtube"))["items_synced"] == 3

    @pytest.mark.asyncio
    async def test_rejects_bad_source(self):
        tools = make_tools(lambda r: json_response({}), enable_sync=True)
        with pytest.raises(RadarError, match="source inválida"):
            await tools.sync("tiktok")


# ─────────────────────────── config ───────────────────────────


class TestSettings:
    def test_defaults_point_at_the_deployed_app(self):
        assert load_settings().api_url.startswith("https://")
        assert "railway.app" in load_settings().api_url

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("RADAR_API_URL", "https://otro.test/")
        monkeypatch.setenv("RADAR_MAX_CONTENT_CHARS", "500")
        monkeypatch.setenv("RADAR_ENABLE_SYNC", "true")
        settings = load_settings()
        assert settings.api_url == "https://otro.test"
        assert settings.max_content_chars == 500
        assert settings.enable_sync is True

    def test_bad_int_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("RADAR_MAX_CONTENT_CHARS", "no-soy-un-numero")
        assert load_settings().max_content_chars == 8_000

    def test_limit_is_capped_at_the_api_max(self, monkeypatch):
        monkeypatch.setenv("RADAR_DEFAULT_LIMIT", "500")
        assert load_settings().default_limit == 50


# ─────────────────────────── capa MCP ───────────────────────────


class TestServerSurface:
    @pytest.mark.asyncio
    async def test_every_tool_is_registered(self):
        tools_listed = await build_server().list_tools()
        names = {t.name for t in tools_listed}
        assert names == {
            "radar_stats",
            "radar_search",
            "radar_get_video",
            "radar_get_article",
            "radar_get_repo",
            "radar_get_paper",
            "radar_get_context",
            "radar_sync",
        }

    @pytest.mark.asyncio
    async def test_every_tool_has_a_description(self):
        """Un agente decide qué herramienta usar leyendo la descripción."""
        for tool in await build_server().list_tools():
            assert tool.description and len(tool.description) > 40, tool.name

    @pytest.mark.asyncio
    async def test_tools_declare_their_parameters(self):
        schema = next(
            t.inputSchema for t in await build_server().list_tools() if t.name == "radar_search"
        )
        assert "query" in schema["properties"]
        assert "since_days" in schema["properties"]

    @pytest.mark.asyncio
    async def test_resources_are_registered(self):
        resources = await build_server().list_resources()
        uris = {str(r.uri) for r in resources}
        assert {"radar://schema", "radar://config", "radar://stats"} <= uris

    @pytest.mark.asyncio
    async def test_schema_resource_documents_content_ids(self):
        text = await build_server().read_resource("radar://schema")
        body = text[0] if isinstance(text, list) else text
        assert "transcript:" in str(body)
        assert "untrusted" in str(body)