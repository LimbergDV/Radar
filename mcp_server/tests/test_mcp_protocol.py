"""Prueba de extremo a extremo del protocolo MCP.

No llama a las funciones sueltas: habla MCP de verdad (tools, recursos,
respuestas) contra la API real. Es lo que se conecta Claude Code, así que si
esto pasa, lo que verrán ellos funciona.

    RADAR_LIVE=1 pytest tests/test_mcp_protocol.py -q
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar_mcp.server import build_server  # noqa: E402
from radar_mcp.tools import VALID_SOURCES  # noqa: E402

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RADAR_LIVE") != "1",
        reason="Requiere la API real. Activa con RADAR_LIVE=1",
    ),
]


def payload_of(result) -> dict:
    """Extrae el dict que devuelve la herramienta vía el protocolo MCP.

    `call_tool` devuelve una lista de bloques de contenido; en el primero va
    el JSON serializado de lo que devolvió la herramienta.
    """
    blocks = result if isinstance(result, list) else [result]
    return json.loads(blocks[0].text)


@pytest.fixture
def server():
    return build_server()


class TestHandshake:
    @pytest.mark.asyncio
    async def test_lists_every_tool(self, server):
        """El conteo exacto envejece mal: se comprueba el conjunto, no el número."""
        tools = await server.list_tools()
        assert {t.name for t in tools} == {
            "radar_stats",
            "radar_search",
            "radar_get_video",
            "radar_get_transcript",
            "radar_get_article",
            "radar_get_repo",
            "radar_get_readme",
            "radar_get_paper",
            "radar_get_context",
            "radar_sync",
        }

    @pytest.mark.asyncio
    async def test_every_tool_documents_its_parameters(self, server):
        """Un agente elige la herramienta leyendo el schema, no adivinando."""
        for tool in await server.list_tools():
            assert tool.inputSchema.get("type") == "object", tool.name
            assert tool.description.strip(), tool.name


class TestAgentJourney:
    """El recorrido que hará un agente real, de principio a fin."""

    @pytest.mark.asyncio
    async def test_discover_then_search_then_read(self, server):
        # 1. Orientar: qué hay.
        stats = payload_of(await server.call_tool("radar_stats", {}))
        assert stats["total_items"] > 0
        assert stats["config"]["github"]["keywords"]

        # 2. Encontrar algo interesante.
        search = payload_of(
            await server.call_tool("radar_search", {"source": "github", "limit": 5})
        )
        assert search["count"] > 0
        full_name = search["items"][0]["title"]

        # 3. Leerlo en detalle.
        detail = payload_of(await server.call_tool("radar_get_repo", {"repo": full_name}))
        assert detail["repo"]["full_name"] == full_name
        assert detail["readme"]["total_chars"] > 0

    @pytest.mark.asyncio
    async def test_long_readme_is_readable_in_chunks(self, server):
        """El caso de los 30k chars: por rangos, no de una."""
        search = payload_of(
            await server.call_tool("radar_search", {"source": "github", "limit": 1})
        )
        full_name = search["items"][0]["title"]
        content_id = f"readme:{full_name}"

        summary = payload_of(await server.call_tool("radar_get_repo", {"repo": full_name}))
        total = summary["readme"]["total_chars"]
        assert total > 1000

        # Referencia: los primeros 4.000 chars pedidos de una vez.
        reference = payload_of(
            await server.call_tool(
                "radar_get_context", {"content_id": content_id, "offset": 0, "limit": 4000}
            )
        )["text"]

        # Ahora los mismos 4.000, troceados de 1.000 en 1.000.
        chunks, offset = [], 0
        while offset < 4000:
            chunk = payload_of(
                await server.call_tool(
                    "radar_get_context",
                    {"content_id": content_id, "offset": offset, "limit": 1000},
                )
            )
            chunks.append(chunk["text"])
            offset = chunk["next_offset"] or offset + 1000

        assert len(chunks) == 4
        assert all(chunks), "un tramo vino vacío"
        assert "".join(chunks) == reference, "trocear cambió el contenido"

    @pytest.mark.asyncio
    async def test_readable_news_end_to_end(self, server):
        """Lo que arreglamos: noticias con texto de verdad."""
        search = payload_of(
            await server.call_tool("radar_search", {"source": "news", "limit": 5})
        )
        readable = 0
        for item in search["items"]:
            article = payload_of(
                await server.call_tool(
                    "radar_get_article",
                    {"article_id": item["source_id"], "content": "full"},
                )
            )
            if article["body"]["available"]:
                readable += 1
                assert article["body"]["untrusted"] is True
        assert readable > 0


def resource_text(contents) -> str:
    """`read_resource` devuelve [ReadResourceContents], cuyo `.content` ya es str."""
    first = contents[0] if isinstance(contents, (list, tuple)) else contents
    content = getattr(first, "content", None)
    if isinstance(content, str):
        return content
    return str(getattr(content, "text", first))


@pytest.mark.asyncio
async def test_schema_resource_is_readable(server):
    text = resource_text(await server.read_resource("radar://schema"))
    assert "transcript:" in text


@pytest.mark.asyncio
async def test_config_resource_is_valid_json(server):
    config = json.loads(resource_text(await server.read_resource("radar://config")))
    # Se compara contra VALID_SOURCES y no contra una lista escrita a mano:
    # la anterior se quedó sin "papers" al añadir esa fuente.
    assert set(config) == set(VALID_SOURCES)
    assert isinstance(config["youtube"]["keywords"], list)


@pytest.mark.asyncio
async def test_stats_resource_is_valid_json(server):
    stats = json.loads(resource_text(await server.read_resource("radar://stats")))
    assert "total_items" in stats


class TestFailuresAreUseful:
    @pytest.mark.asyncio
    async def test_unknown_repo_keeps_an_actionable_message(self, server):
        """El error tiene que llegar al agente con el consejo, no como stacktrace."""
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError) as excinfo:
            await server.call_tool("radar_get_repo", {"repo": "nada/aqui"})

        message = str(excinfo.value)
        assert "radar_search" in message
        assert "no encontré" in message.lower()