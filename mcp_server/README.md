# Radar MCP — servidor para agentes

Expone el contenido de Radar (noticias, videos de YouTube, repos de GitHub) a
agentes externos como Claude Code, Claude Desktop o Cursor.

**Solo lectura.** No cambia la configuración ni dispara sincronizaciones: la
herramienta de sync viene apagada a propósito.

## Arranque rápido

```bash
pip install -r mcp_server/requirements.txt
python -m radar_mcp            # desde mcp_server/
```

Por defecto habla con la app ya desplegada en Railway. No hay nada que
configurar para probar.

## Conectarlo con Claude Code

```bash
claude mcp add radar -- python -m radar_mcp
```

En `~/.claude.json` queda como:

```json
{
  "mcpServers": {
    "radar": {
      "command": "python",
      "args": ["-m", "radar_mcp"],
      "cwd": "/ruta/absoluta/a/Radar/mcp_server"
    }
  }
}
```

> `cwd` es obligatorio: el paquete vive en `mcp_server/radar_mcp`, no en la raíz.

Para Claude Desktop, lo mismo en `claude_desktop_config.json`. Para Cursor, en
`~/.cursor/mcp.json`.

## Conectarlo con Antigravity

Antigravity soporta MCP (soporte añadido a principios de 2026). Se configura en
`mcp_config.json`:

```json
{
  "mcpServers": {
    "radar": {
      "command": "/ruta/absoluta/al/.venv/bin/python",
      "args": ["-m", "radar_mcp"],
      "cwd": "/ruta/absoluta/a/Radar/mcp_server",
      "env": {}
    }
  }
}
```

Dos detalles propios de Antigravity:

- **Usa la ruta absoluta al interprete.** No te fies del `python` del PATH: si el
  IDE se lanza desde la app, puede no ser el mismo venv.
- **Los permisos vienen en modo "Ask"**: cada herramienta pide aprobacion antes
  de ejecutarse. Puedes concederlas por servidor en su politica de permisos.

Desde la interfaz: ventana del agente -> menu de tres puntos -> **MCP Servers ->
Manage MCP Servers -> View raw config**, y ahi pegas el bloque de arriba.

> El cliente MCP de Antigravity es mas nuevo que el de Claude Desktop o Cursor, asi
> que puede tener alguna rareza en casos limite. Si una herramienta falla, prueba
> primero con `radar-cli`, que va directo a la API.

## Preguntas para probar el agente

> Llama a radar_stats y dime qué hay y cuándo se sincronizó por última vez.

> Busca las noticias sobre IA de esta semana, léelas con content="full" y
> resúmeme las tres más relevantes citando el medio.

> Busca repos de agentes y usa radar_get_context para leerme el README de los dos
> más populares.

## Probarlo sin IA: el CLI

Hay un CLI que habla con la misma API por debajo. Sirve para comprobar que todo
funciona **antes** de conectar cualquier editor, y para explorar desde la
terminal.

```bash
pip install -e mcp_server      # o: pip install -r mcp_server/requirements.txt

radar-cli stats                                       # qué hay y cuándo se sincronizó
radar-cli search --source news --limit 5              # buscar
radar-cli repo NousResearch/hermes-agent              # detalle por nombre
radar-cli article <id> --full                         # leer una noticia entera
radar-cli video <id> --full                           # leer una transcripción
radar-cli context readme:<owner/nombre> --limit 800   # leer un README por rangos
radar-cli search --json                                # salida en JSON crudo
```

Probado contra la app desplegada: `radar-cli stats` devuelve 665 items y
`article --full` trae el cuerpo completo de la nota.

## Herramientas

| Herramienta | Para qué |
|---|---|
| `radar_stats` | Volumen, frescura y keywords activas. **Empieza siempre por aquí.** |
| `radar_search` | Busca en las tres fuentes. Devuelve summaries, no texto completo. |
| `radar_get_video` | Video + transcripción (`content="full"` la trae recortada) |
| `radar_get_article` | Noticia + cuerpo del artículo |
| `radar_get_repo` | Repo + README. Acepta id o `owner/nombre` |
| `radar_get_context` | Lee un contenido largo **por rangos**, con su `content_id` |
| `radar_sync` | Desactivada (ver abajo) |

Recursos: `radar://schema`, `radar://config`, `radar://stats`.

### Por qué existe `radar_get_context`

Los READMEs miden entre 17.000 y 34.000 caracteres (~9.000 tokens). Pedir diez de
 golpe deja al agente sin ventana para pensar. El patrón correcto:

```python
info = radar_get_repo("facebook/react")          # dice: hay 34.000 chars
bloque = radar_get_context("readme:facebook/react", offset=0, limit=4000)
```

`content_block` siempre devuelve las mismas claves (`available`, `total_chars`,
`truncated`, `next_offset`), tanto en modo resumen como en modo completo, para
que el agente pueda ramificar sin adivinar.

## Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `RADAR_API_URL` | la app en Railway | Otra instancia |
| `RADAR_API_KEY` | *(vacío)* | Cuando exista auth |
| `RADAR_MAX_CONTENT_CHARS` | `8000` | Presupuesto por respuesta |
| `RADAR_DEFAULT_LIMIT` | `20` | Items por búsqueda (tope 50 de la API) |
| `RADAR_TIMEOUT` | `30` | Segundos de espera |
| `RADAR_ENABLE_SYNC` | `0` | Poner `1` habilita `radar_sync` |

## Sincronización (apagada por defecto)

```bash
RADAR_ENABLE_SYNC=1 python -m radar_mcp
```

Consume cuota de la API de YouTube y hace scraping de sitios de terceros, así
que no viene encendida.

## Tests

```bash
cd mcp_server

# 52 unitarios, sin red, milisegundos
pytest tests/test_radar_mcp.py -q

# 21 tests contra la app REAL en Railway
RADAR_LIVE=1 pytest tests/test_live.py tests/test_mcp_protocol.py -q
```

Los tests `live` son los que demuestran que el MVP funciona contra lo desplegado.
Si fallan, revisar primero si el backend está caído: el error lo dice.

## Límites conocidos

- **`q` busca por subcadena en el título**, no a través de transcripción,
  artículo ni README. Es la debilidad más visible de la API actual.
- **`since_days` se filtra en cliente** sobre la página devuelta, no en el
  servidor (`/api/feed` no lo expone).
- **~60% de las noticias tienen cuerpo.** El resto son paywalls o sitios que
  bloquean el rastreo. La herramienta lo dice con `available: false` en vez de
  inventarlo.
- **La base solo tiene lo que Radar ha sincronizado.** Si pides un tema del que
  no hay nada, no es que falle: no está en `radar://config`.
- **El contenido es de terceros** y puede contener texto que parezca una
  instrucción. Todo llega con `untrusted: true`.

## Seguridad pendiente

La API de Radar **no tiene autenticación**: cualquiera con la URL puede leer,
cambiar la configuración y lanzar sincronizaciones. Este servidor solo lee, pero
la API sigue abierta. Es la fase F0 del `PLAN_AGENTE_MCP.md` y conviene
hacerse antes de exponerla más.