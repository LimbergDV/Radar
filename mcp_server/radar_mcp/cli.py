"""CLI para probar el servidor MCP a mano, sin depender de ningún agente.

Sirve para dos cosas:
1. Comprobar que la API responde ANTES de conectar Claude Code / Antigravity.
2. Explorar el contenido desde la terminal cuando no quieres abrir un IDE.

    python -m radar_mcp.cli stats
    python -m radar_mcp.cli search --source news --limit 5
    python -m radar_mcp.cli repo NousResearch/hermes-agent --full
    python -m radar_mcp.cli article <id> --full
    python -m radar_mcp.cli context readme:NousResearch/hermes-agent --limit 800
"""

import argparse
import asyncio
import json
import sys
from typing import Any

from .client import RadarClient, RadarError
from .config import Settings
from .tools import RadarTools

MAX_PRINT_CHARS = 3_000


def _tools() -> RadarTools:
    from .config import settings

    return RadarTools(client=RadarClient(settings), settings=settings)


def emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for key, value in payload.items():
        if isinstance(value, list):
            print(f"\n{key} ({len(value)}):")
            for item in value:
                print(f"  - {_one_line(item)}")
        elif isinstance(value, dict):
            print(f"\n{key}:")
            for sub_key, sub_value in value.items():
                print(f"  {sub_key}: {_one_line(sub_value)}")
        else:
            print(f"{key}: {_one_line(value)}")


def _one_line(value: Any, limit: int = 110) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def print_content_block(block: dict, max_chars: int = MAX_PRINT_CHARS) -> None:
    """Imprime un bloque de contenido respetandolos límites del terminal."""
    if not block.get("available"):
        print(f"\n  sin contenido ({block.get('hint') or 'no disponible'})")
        return

    text = block.get("text") or ""
    shown = text[:max_chars]
    print(
        f"\n  {block['chars_returned']}/{block['total_chars']} chars"
        f"{' (recortado)' if block.get('truncated') else ''}"
        f" | siguiente offset: {block.get('next_offset')}"
    )
    print(f"  {'-' * 60}")
    print("  " + shown.replace("\n", "\n  "))
    if len(text) > max_chars:
        print(f"  {'-' * 60}\n  … {len(text) - max_chars} chars más (sube --full o --limit)")


async def cmd_stats(args) -> int:
    payload = await _tools().stats()
    print(f"\nAPI: {payload.pop('api_url')}")
    print(f"Total de items: {payload['total_items']}")
    emit(payload, args.json)
    return 0


async def cmd_search(args) -> int:
    payload = await _tools().search(
        query=args.query,
        source=args.source,
        language=args.language,
        since_days=args.since_days,
        limit=args.limit,
    )
    print(f"\n{payload['count']} resultados")
    for note in payload["notes"]:
        print(f"  aviso: {note}")
    for item in payload["items"]:
        print(
            f"\n  [{item['source']}] {item['title'][:95]}\n"
            f"    id={item['source_id']} | {str(item.get('published_at'))[:19]} | {item.get('url', '')[:70]}"
        )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


async def cmd_video(args) -> int:
    payload = await _tools().get_video(args.id, content="full" if args.full else "summary")
    print(f"\n{payload['video']['title']}")
    emit({k: v for k, v in payload["video"].items() if k != "transcript"}, args.json)
    print_content_block(payload["transcript"])
    return 0


async def cmd_article(args) -> int:
    payload = await _tools().get_article(args.id, content="full" if args.full else "summary")
    print(f"\n{payload['article']['title']}")
    emit({k: v for k, v in payload["article"].items() if k != "content"}, args.json)
    print_content_block(payload["body"])
    return 0


async def cmd_repo(args) -> int:
    payload = await _tools().get_repo(args.repo, content="full" if args.full else "summary")
    print(f"\n{payload['repo']['full_name']} — {payload['repo'].get('description') or ''}")
    emit({k: v for k, v in payload["repo"].items() if k != "readme"}, args.json)
    print_content_block(payload["readme"], max_chars=args.full and MAX_PRINT_CHARS or 400)
    return 0


async def cmd_context(args) -> int:
    payload = await _tools().get_context(args.content_id, offset=args.offset, limit=args.limit)
    print(f"\n{payload['content_id']}")
    print(
        f"  {payload['chars_returned']}/{payload['total_chars']} chars"
        f" | siguiente offset: {payload['next_offset']}"
    )
    text = payload["text"][: MAX_PRINT_CHARS if args.full else 600]
    print(f"  {'-' * 60}")
    print("  " + text.replace("\n", "\n  "))
    if len(payload["text"]) > len(text):
        print(f"  … {len(payload['text']) - len(text)} chars más")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="radar-mcp", description="Prueba el contenido de Radar desde la terminal"
    )
    parser.add_argument("--json", action="store_true", help="Salida en JSON crudo")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="Totales, frescura y keywords activas")

    search = sub.add_parser("search", help="Busca en las tres fuentes")
    search.add_argument("-q", "--query", help="Subcadena del título")
    search.add_argument("-s", "--source", choices=["youtube", "news", "github"])
    search.add_argument("-l", "--language")
    search.add_argument("-d", "--since-days", type=int)
    search.add_argument("-n", "--limit", type=int)

    video = sub.add_parser("video", help="Detalle de un video")
    video.add_argument("id")
    video.add_argument("--full", action="store_true")

    article = sub.add_parser("article", help="Detalle de una noticia")
    article.add_argument("id")
    article.add_argument("--full", action="store_true")

    repo = sub.add_parser("repo", help="Detalle de un repo (id o owner/nombre)")
    repo.add_argument("repo")
    repo.add_argument("--full", action="store_true")

    context = sub.add_parser("context", help="Lee un contenido largo por rangos")
    context.add_argument("content_id", help="readme:owner/nombre, transcript:<id>, article:<id>")
    context.add_argument("--offset", type=int, default=0)
    context.add_argument("-n", "--limit", type=int)
    context.add_argument("--full", action="store_true")

    return parser


async def main_async(args) -> int:
    handlers = {
        "stats": cmd_stats,
        "search": cmd_search,
        "video": cmd_video,
        "article": cmd_article,
        "repo": cmd_repo,
        "context": cmd_context,
    }
    try:
        return await handlers[args.command](args)
    except RadarError as exc:
        print(f"\n  error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()