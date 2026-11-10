# Imagen del servidor MCP de Radar para Railway.
#
# Railway construye desde la raíz del servicio, que debe ser `mcp_server`.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Primero las dependencias para que la capa se reutilice.
COPY pyproject.toml README.md ./
COPY radar_mcp/__init__.py ./radar_mcp/
RUN pip install --no-cache-dir .

COPY radar_mcp ./radar_mcp

# Railway inyecta PORT y espera 0.0.0.0. `--http` sin valor lee $PORT, y el
# servidor ya hace bind a 0.0.0.0: sin esto el servicio no recibe trafico.
EXPOSE 8000
CMD ["python", "-m", "radar_mcp", "--http"]