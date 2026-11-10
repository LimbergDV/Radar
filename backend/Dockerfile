# Imagen del backend para Railway.
#
# Railway detecta el Dockerfile automaticamente en el Root Directory del
# servicio (backend/). El servicio debe escuchar en :: (todas las interfaces
# IPv4 e IPv6) y en $PORT, que Railway inyecta por entorno.

FROM python:3.12-slim

# Sin buffering: los logs tienen que llegar a Railway en cuanto se escriben, si
# no el deploy parece colgado aunque la app este bien.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Primero las dependencias para que la capa se reutilice mientras no cambie
# requirements.txt; si se copiase todo el codigo antes, cada cambio de un .py
# reinstalaria ~100 paquetes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Las migraciones se aplican en cada arranque. Con UNA sola replica es lo
# correcto y evita olvidar el paso; si se escala a varias, esto puede correr en
# paralelo y convendria moverlo a un job de release.
#
# --proxy-headers hace que uvicorn confíe en X-Forwarded-* y req.url.app sea el
# dominio publico, no el host interno.
#
# --host 0.0.0.0: la red privada de Railway ya es dual-stack (IPv4 + IPv6), pero
# el healthcheck y el proxy del edge llegan por IPv4. Con `--host ::` uvicorn
# solo abria el socket IPv6 en este runtime y el deploy moria con
# "Healthcheck failed ... service unavailable" aunque la app estuviera viva.
# 0.0.0.0 cubre IPv4 y, en entornos dual-stack, tambien el trafico interno.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]