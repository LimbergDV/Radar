export const environment = {
  production: true,
  // En producción la API se sirve en el mismo origen (proxy inverso), así que
  // basta con la ruta relativa. Si se despliega aparte, cambia aquí el host.
  apiUrl: '/api',
  healthPollMs: 60_000,
};