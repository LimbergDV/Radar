# Frontend Angular para Railway: se compila y lo sirve nginx.
#
# nginx hace doble trabajo: sirve los estaticos con fallback de SPA (las rutas
# /news/:id etc. son cliente) y hace de proxy inverso hacia el backend para
# /api y /health. Asi el navegador solo ve un origen, y no hace falta CORS.

# ── 1. Build ──
FROM node:22-alpine AS build

WORKDIR /app

# npm ci usa package-lock.json: build reproducible, y falla si el lock no cuadra
# con el package.json en lugar de resolver versiones nuevas en produccion.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# ── 2. Servidor ──
FROM nginx:1.27-alpine

# La plantilla va FUERA de /etc/nginx/templates/ a proposito. Si se dejara
# ahi, el entrypoint de la imagen oficial la sustituiria por su cuenta con
# envsubst; funciona, pero aqui el render es explicito (ver el entrypoint) para
# no depender de como ese script decide que variables toca.
COPY nginx.conf.template /etc/nginx/radar.conf.template
COPY docker-entrypoint.sh /usr/local/bin/radar-entrypoint.sh
RUN chmod +x /usr/local/bin/radar-entrypoint.sh
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 80

# El entrypoint detecta el resolver del contenedor (Railway usa IPv6, Docker
# local 127.0.0.11), arma el upstream dinamico desde BACKEND_URL y renderiza
# nginx. Se hace en runtime, no en build: Railway inyecta esas variables al
# desplegar. Con `resolver` + variable, nginx re-resuelve la IP del backend en
# cada request y un redeploy ya no deja el frontend en 502.
ENTRYPOINT ["/usr/local/bin/radar-entrypoint.sh"]
CMD []