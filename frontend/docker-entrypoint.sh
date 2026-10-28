#!/bin/sh
# Arranque del frontend: detecta el resolver del contenedor, arma el upstream
# dinamico y renderiza nginx. Se hace en runtime (no en build) porque Railway
# inyecta BACKEND_URL y el DNS interno al desplegar.
set -eu

: "${BACKEND_URL:?BACKEND_URL no esta definido en el servicio frontend}"

# BACKEND_URL llega como http://radar.railway.internal:8000. Para proxy_pass
# con variable separamos esquema y host:puerto; el host se resuelve por request.
case "$BACKEND_URL" in
  http://*)  BACKEND_SCHEME=http;  BACKEND_UPSTREAM="${BACKEND_URL#http://}" ;;
  https://*) BACKEND_SCHEME=https; BACKEND_UPSTREAM="${BACKEND_URL#https://}" ;;
  *)         BACKEND_SCHEME=http;  BACKEND_UPSTREAM="$BACKEND_URL" ;;
esac
BACKEND_UPSTREAM="${BACKEND_UPSTREAM%/}"
export BACKEND_SCHEME BACKEND_UPSTREAM

# El resolver NO es siempre 127.0.0.11: eso es Docker local. En Railway el
# nameserver es IPv6 y nginx lo exige entre corchetes. Se lee del contenedor.
NS="$(awk '/^[[:space:]]*nameserver[[:space:]]/ { print $2; exit }' /etc/resolv.conf 2>/dev/null || true)"
case "$NS" in
  "")  NS="[fd12::10]" ;;   # fallback documentado de la red privada de Railway
  *:*) NS="[$NS]" ;;
esac
export NGINX_RESOLVER="$NS"

# Lista explicita: si envsubst ve $request_uri, $host o $proxy_host (variables
# de nginx, no del entorno), las borra y rompe el proxy y el fallback de SPA.
envsubst '${BACKEND_SCHEME} ${BACKEND_UPSTREAM} ${NGINX_RESOLVER}' \
  < /etc/nginx/radar.conf.template > /etc/nginx/conf.d/default.conf

echo "radar-frontend: backend=${BACKEND_SCHEME}://${BACKEND_UPSTREAM} resolver=${NGINX_RESOLVER}"

nginx -t
exec nginx -g 'daemon off;'
