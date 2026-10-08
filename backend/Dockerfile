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
# --host :: hace que uvicorn escuche en todas las interfaces IPv4 e IPv6 (y en
# $PORT). La red privada de Railway resuelve los servicios a direcciones IPv6,
# asi que con 0.0.0.0 (solo IPv4) las conexiones desde otros servicios caducan.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host :: --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]