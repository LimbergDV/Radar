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
# envsubst; funciona, pero aqui el render es explicito (ver CMD) para no
# depender de como ese script decide que variables toca.
COPY nginx.conf.template /etc/nginx/radar.conf.template
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 80

# envsubst CON lista explicita: sustituye unicamente ${BACKEND_URL}.
# Sin lista, envsubst se come tambien $uri, $host y $scheme (que son variables
# de nginx, no del entorno) y el `try_files` de la SPA queda vacio -> 404 al
# recargar en /news/abc. Las comillas simples evitan que sea el propio shell
# quien expanda ${BACKEND_URL} antes de tiempo.
CMD ["sh", "-c", "envsubst '${BACKEND_URL}' < /etc/nginx/radar.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]