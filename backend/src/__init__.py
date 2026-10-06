"""NewsRadar backend — Clean Architecture.

- core/            → entidades, interfaces de repositorio y casos de uso (sin dependencias externas)
- infrastructure/  → PostgreSQL, APIs externas, scheduler
- application/     → DTOs y servicios orquestadores
- presentation/    → routers FastAPI
"""