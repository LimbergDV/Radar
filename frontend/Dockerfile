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

# Default del resolver DNS de Railway. Se declara como ENV (y no como
# ${DNS_RESOLVER:-...} en el CMD) porque envsubst recibe una lista de NOMBRES
# de variable: si el shell le pasa el valor, no hay nada que sustituir y queda
# "resolver ${DNS_RESOLVER}", sintaxis invalida -> nginx no arranca y el
# frontend se cae entero, no solo /api. Con ENV siempre hay valor, y Railway
# lo puede sobreescribir si su /etc/resolv.conf usa otro.
ENV DNS_RESOLVER=127.0.0.11

# envsubst con lista EXPLICITA de variables: sustituye solo BACKEND_URL y
# DNS_RESOLVER. Sin lista, envsubst se come tambien $uri, $host, $scheme y
# $request_uri (que son variables de nginx, no del entorno) y el `try_files`
# de la SPA queda vacio -> 404 al recargar en /news/abc.
# Las comillas simples dejan los nombres intactos hasta envsubst.
CMD ["sh", "-c", "envsubst '${BACKEND_URL} ${DNS_RESOLVER}' < /etc/nginx/radar.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]