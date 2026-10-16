# 📰 NewsRadar — Plan de Desarrollo v2.0
> Réplica evolucionada del proyecto **Newsss** (Next.js + SQLite + Prisma)  
> Stack nuevo: **Angular 19** (frontend) + **Python FastAPI** (backend) + **PostgreSQL** + **SQLAlchemy**

---

## 1. Análisis del Proyecto Original (Newsss)

### ¿Qué hace?
Es un **agregador de noticias sobre IA** que consume múltiples fuentes en tiempo real y las muestra en un feed unificado.

### Fuentes de datos implementadas
| Fuente | Qué extrae | API/Método |
|--------|-----------|------------|
| **YouTube** | Videos recientes sobre IA (keywords + canales) | YouTube Data API v3 — búsqueda en 4 fases |
| **Google News** | Artículos RSS sobre IA (ES + EN) | Google News RSS Feed + decodificación de URLs |
| **GitHub** | Repositorios trending de IA | GitHub REST API |
| **X / Twitter** | Posts *(próximamente)* | — |
| **LinkedIn** | Posts *(próximamente)* | — |

### Arquitectura original (Next.js)
```
newsss/
├── app/                        # Next.js App Router (páginas SSR)
│   ├── page.tsx                # Home — feed principal con tabs
│   └── settings/page.tsx       # Config de búsqueda por fuente
├── features/
│   └── {fuente}/
│       ├── data/
│       │   ├── {fuente}.entity.ts       # Clase de dominio
│       │   ├── {fuente}.fetcher.ts      # Lógica de fetch externo
│       │   ├── {fuente}.db.ts           # Acceso a SQLite (Prisma)
│       │   └── {fuente}.config.db.ts    # Configuración singleton en DB
│       ├── {fuente}.controller.ts       # Server Actions de Next.js
│       └── presentation/               # Componentes React (cards, modals, forms)
├── components/                 # Componentes compartidos (FeedSection, UI)
├── prisma/schema.prisma        # Modelos: YouTubeVideo, GoogleNewsArticle, GitHubData + configs
└── lib/prisma.ts               # Singleton del cliente Prisma
```

### Modelos de datos clave (SQLite/Prisma)
- **YouTubeVideo** — id, title, channel, publishedAt, url, thumbnailUrl, transcript, views, likes, comments
- **YouTubeSearchConfig** — keywords[], channelIds[], languages[], maxResults, lastSearchAt *(singleton)*
- **GoogleNewsArticle** — id(guid), title, link, pubDate, sourceName, sourceUrl, imageUrl?, content?
- **GoogleNewsConfig** — q, hl, gl, ceid, when, site, intitle, maxResults, lastSearchAt *(singleton)*
- **GitHubData** — id, name, fullName, htmlUrl, description, stars, language, topics[], readme, forks, issues, license
- **GitHubDataConfig** — keywords[], daysActive, minStars, minForks, requireLicense, topics[], languages[], maxResults *(singleton)*

### Lógica de negocio destacada
1. **Pipeline YouTube** (4 fases): resolver handles → buscar candidatos (concurrente por idioma) → enriquecer en batch → filtrar + transcribir
2. **Google News RSS**: fetch dual ES/EN concurrente → deduplicar → enriquecer con imagen y contenido (Readability) en chunks
3. **Auto-sync**: si la DB está vacía y `lastSearchAt` > 1h, sincroniza automáticamente al cargar
4. **Config singleton**: cada fuente tiene una tabla de configuración con un único registro (id=1)

---

## 2. Stack Tecnológico Propuesto (v2.0)

### Por qué este stack

| Decisión | Justificación |
|----------|--------------|
| **Angular 19** | Framework enterprise, tipado estricto, DI nativa (ideal con Clean Architecture), signals, standalone components |
| **FastAPI (Python)** | Async nativo, validación con Pydantic, documentación automática (OpenAPI), ideal para pipelines de scraping/IA |
| **PostgreSQL** | Producción-ready, mejor que SQLite para concurrencia, JSONB para arrays, full-text search nativo |
| **SQLAlchemy 2.0 + Alembic** | ORM potente equivalente a Prisma en Python, migraciones con Alembic (≈ Prisma Migrate) |
| **Pydantic v2** | Equivalente a Zod/TypeScript types — validación y serialización de schemas |
| **APScheduler** | Scheduler en Python para auto-sync periódico (equivalente al "1h check" del original) |
| **Angular Material / TailwindCSS** | UI moderna con design system consistente |

### Stack completo

**Backend (Python)**
- `fastapi` + `uvicorn[standard]`
- `sqlalchemy[asyncio]` + `asyncpg`
- `alembic` (migraciones)
- `pydantic-settings` (variables de entorno)
- `httpx` (cliente HTTP async)
- `feedparser` / `lxml` (RSS parsing)
- `apscheduler` (sync automático)
- `google-auth` / `youtube-transcript-api`
- `beautifulsoup4` + `trafilatura` (extracción de contenido — mejor que Readability)
- `pytest` + `pytest-asyncio`

**Frontend (TypeScript)**
- `@angular/core` 19 (standalone, signals)
- `@angular/material` (componentes UI)
- `tailwindcss` + `@tailwindcss/typography`
- `lucide-angular`
- `@ngrx/signals` (state management con Signal Store)
- `rxjs`

---

## 3. Clean Architecture — Estructura del Proyecto

```
newsradar/
├── backend/                          # FastAPI
│   ├── src/
│   │   ├── core/                     # Capa de Dominio (no depende de nada externo)
│   │   │   ├── entities/             # Entidades puras (dataclasses/Pydantic)
│   │   │   │   ├── youtube.py
│   │   │   │   ├── google_news.py
│   │   │   │   ├── github.py
│   │   │   │   └── source_config.py
│   │   │   ├── repositories/         # Interfaces (Abstract Base Classes)
│   │   │   │   ├── youtube_repository.py
│   │   │   │   ├── google_news_repository.py
│   │   │   │   └── github_repository.py
│   │   │   └── use_cases/            # Casos de uso (lógica de negocio pura)
│   │   │       ├── sync_youtube.py
│   │   │       ├── sync_google_news.py
│   │   │       ├── sync_github.py
│   │   │       └── update_source_config.py
│   │   │
│   │   ├── infrastructure/           # Capa de Infraestructura
│   │   │   ├── database/
│   │   │   │   ├── models.py         # SQLAlchemy ORM models
│   │   │   │   ├── session.py        # Async session factory
│   │   │   │   └── repositories/     # Implementaciones concretas de los repos
│   │   │   │       ├── youtube_pg_repo.py
│   │   │   │       ├── google_news_pg_repo.py
│   │   │   │       └── github_pg_repo.py
│   │   │   ├── external/             # Clientes de APIs externas
│   │   │   │   ├── youtube_api.py    # YouTube Data API v3
│   │   │   │   ├── google_news_rss.py
│   │   │   │   └── github_api.py
│   │   │   └── scheduler/
│   │   │       └── sync_jobs.py      # APScheduler jobs
│   │   │
│   │   ├── application/              # Capa de Aplicación (DTOs + servicios)
│   │   │   ├── dtos/
│   │   │   │   ├── youtube_dto.py
│   │   │   │   ├── google_news_dto.py
│   │   │   │   └── github_dto.py
│   │   │   └── services/             # Orquestadores (inyectan repos + casos de uso)
│   │   │       ├── youtube_service.py
│   │   │       ├── google_news_service.py
│   │   │       └── github_service.py
│   │   │
│   │   └── presentation/             # Capa de Presentación (API REST)
│   │       ├── routers/
│   │       │   ├── youtube_router.py
│   │       │   ├── google_news_router.py
│   │       │   ├── github_router.py
│   │       │   └── config_router.py
│   │       └── dependencies.py       # FastAPI DI (get_db, get_service, etc.)
│   │
│   ├── alembic/                      # Migraciones de DB
│   ├── tests/
│   ├── main.py                       # App entry point
│   ├── pyproject.toml
│   └── .env
│
└── frontend/                         # Angular 19
    ├── src/
    │   ├── app/
    │   │   ├── core/                 # Servicios singleton, guards, interceptors
    │   │   │   ├── services/
    │   │   │   │   ├── youtube.service.ts
    │   │   │   │   ├── google-news.service.ts
    │   │   │   │   └── github.service.ts
    │   │   │   └── interceptors/
    │   │   │       └── api.interceptor.ts
    │   │   ├── shared/               # Componentes, pipes, directivas reutilizables
    │   │   │   ├── components/
    │   │   │   │   ├── article-card/
    │   │   │   │   ├── video-card/
    │   │   │   │   ├── repo-card/
    │   │   │   │   └── skeleton-loader/
    │   │   │   └── pipes/
    │   │   │       ├── time-ago.pipe.ts
    │   │   │       └── format-number.pipe.ts
    │   │   ├── features/             # Feature modules (lazy loaded)
    │   │   │   ├── feed/             # Página principal
    │   │   │   │   ├── feed.component.ts
    │   │   │   │   ├── feed.store.ts   # NgRx Signal Store
    │   │   │   │   └── feed.routes.ts
    │   │   │   ├── youtube/
    │   │   │   │   ├── youtube-list.component.ts
    │   │   │   │   └── youtube-detail.component.ts  # ← NUEVO: ver transcripción
    │   │   │   ├── google-news/
    │   │   │   ├── github/
    │   │   │   └── settings/
    │   │   │       ├── settings.component.ts
    │   │   │       └── source-config-form/
    │   │   ├── layout/
    │   │   │   ├── navbar/
    │   │   │   └── sidebar/           # ← NUEVO: navegación lateral
    │   │   └── app.routes.ts
    │   ├── environments/
    │   └── styles/
    ├── angular.json
    ├── tsconfig.json
    └── package.json
```

---

## 4. Endpoints de la API (FastAPI)

### YouTube
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/youtube/videos` | Listar videos (paginados) |
| `GET` | `/api/youtube/videos/{id}` | Detalle de video + transcripción completa |
| `POST` | `/api/youtube/sync` | Disparar sincronización manual |
| `GET` | `/api/youtube/config` | Obtener configuración de búsqueda |
| `PUT` | `/api/youtube/config` | Actualizar configuración |

### Google News
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/news/articles` | Listar artículos (paginados, filtro por idioma) |
| `GET` | `/api/news/articles/{id}` | Detalle de artículo |
| `POST` | `/api/news/sync` | Disparar sincronización manual |
| `GET` | `/api/news/config` | Obtener configuración |
| `PUT` | `/api/news/config` | Actualizar configuración |

### GitHub
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/github/repos` | Listar repositorios (paginados, filtros) |
| `GET` | `/api/github/repos/{id}` | Detalle + README completo |
| `POST` | `/api/github/sync` | Disparar sincronización manual |
| `GET` | `/api/github/config` | Obtener configuración |
| `PUT` | `/api/github/config` | Actualizar configuración |

### General
| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/feed` | Feed unificado (un item de cada fuente) |
| `GET` | `/api/feed/stats` | Estadísticas generales (totales, última sync) |
| `GET` | `/health` | Health check |

---

## 5. Modelos de Base de Datos (PostgreSQL / SQLAlchemy)

```python
# YouTube
class YouTubeVideo(Base):
    id: str (PK)
    title: str
    channel: str
    channel_id: str          # ← NUEVO: para filtrar por canal
    published_at: datetime
    url: str
    thumbnail_url: str
    transcript: str
    views: int
    likes: int
    comments: int
    duration_seconds: int    # ← NUEVO: duración en segundos
    language: str            # ← NUEVO: idioma detectado
    synced_at: datetime

class YouTubeSearchConfig(Base):
    id: int (singleton, PK)
    keywords: list[str]      # JSONB en Postgres (nativo)
    channel_ids: list[str]   # JSONB
    languages: list[str]     # JSONB
    max_results: int
    last_search_at: datetime | None
    updated_at: datetime

# Google News
class GoogleNewsArticle(Base):
    id: str (PK, guid del RSS)
    title: str
    link: str
    pub_date: datetime
    source_name: str
    source_url: str
    image_url: str | None
    content: str | None
    language: str            # ← NUEVO: 'es' | 'en'
    fetched_at: datetime

class GoogleNewsConfig(Base):
    id: int (singleton, PK)
    q: str
    hl: str
    gl: str
    ceid: str
    when: str
    site: str
    intitle: str
    max_results: int
    last_search_at: datetime | None
    updated_at: datetime

# GitHub
class GitHubRepo(Base):
    id: int (PK)
    name: str
    full_name: str
    html_url: str
    description: str
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    language: str
    license: str | None
    topics: list[str]        # JSONB
    readme: str
    owner_avatar_url: str | None
    updated_at: datetime
    synced_at: datetime

class GitHubSearchConfig(Base):
    id: int (singleton, PK)
    keywords: list[str]
    days_active: int
    min_stars: int
    min_forks: int
    require_license: bool
    selected_topics: list[str]
    selected_languages: list[str]
    max_results: int
    last_search_at: datetime | None
    updated_at: datetime
```

---

## 6. Nuevas Funcionalidades (más allá del original)

### 🆕 Funcionalidades añadidas

| Feature | Descripción | Prioridad |
|---------|-------------|-----------|
| **Página de detalle por item** | Vista expandida para video, artículo o repo con contenido completo | Alta |
| **Paginación real** | El original carga todo; v2 usa paginación server-side (cursor/offset) | Alta |
| **Filtros y búsqueda** | Filtrar por fuente, idioma, fecha, keyword en frontend | Alta |
| **Sidebar de navegación** | Reemplazar tabs planos por sidebar lateral más navegable | Media |
| **Dark/Light mode** | Toggle de tema persistido en localStorage | Media |
| **Estadísticas del feed** | Dashboard con conteos, última sync, fuente más activa | Media |
| **Sync automático configurable** | APScheduler con intervalo editable (no solo 1h fija) | Media |
| **Skeleton loaders** | UX de carga más profesional | Media |
| **Notificaciones toast** | Feedback de sync exitoso/fallido en Angular Material | Media |
| **Búsqueda global** | Buscar en todas las fuentes simultáneamente desde un input | Baja |
| **Favoritos** | Marcar items como favoritos (guardados en localStorage o DB) | Baja |
| **Export** | Exportar resultados a JSON/CSV | Baja |

---

## 7. Fases de Desarrollo

### Fase 1 — Fundaciones (Backend)
> Objetivo: tener la API base funcionando con PostgreSQL

- [ ] Setup del proyecto FastAPI (`main.py`, CORS, lifespan, health check)
- [ ] Configuración de PostgreSQL + SQLAlchemy async + Alembic
- [ ] Entidades de dominio (`core/entities/`)
- [ ] Interfaces de repositorio (`core/repositories/`)
- [ ] Modelos ORM (`infrastructure/database/models.py`)
- [ ] Implementaciones de repositorios PostgreSQL
- [ ] DTOs con Pydantic v2
- [ ] Variables de entorno con `pydantic-settings`

### Fase 2 — Lógica de Negocio (Backend)
> Objetivo: replicar y mejorar los pipelines de fetch

- [ ] **YouTube pipeline** (4 fases idénticas pero en Python async con httpx)
  - Resolver handles de canales
  - Búsqueda concurrente por idioma (`asyncio.gather`)
  - Enriquecimiento en batch
  - Filtrado + transcripción (`youtube-transcript-api`)
- [ ] **Google News pipeline** (RSS dual ES/EN + `trafilatura` para contenido)
- [ ] **GitHub pipeline** (GitHub REST API)
- [ ] Casos de uso (`core/use_cases/`)
- [ ] Servicios de aplicación
- [ ] Routers FastAPI con todos los endpoints
- [ ] APScheduler para auto-sync

### Fase 3 — Frontend Angular (Base)
> Objetivo: tener el feed funcionando conectado al backend

- [ ] Setup Angular 19 con standalone components y routing lazy
- [ ] Configuración de TailwindCSS + Angular Material
- [ ] `HttpClient` + interceptor de API base URL
- [ ] Servicios HTTP para cada fuente
- [ ] Signal Store (`feed.store.ts`) — estado global del feed
- [ ] Componentes de card reutilizables (video, artículo, repo)
- [ ] Página de feed principal con tabs + skeleton loaders
- [ ] Navbar + Sidebar de navegación
- [ ] Dark/Light mode toggle

### Fase 4 — Funcionalidades Avanzadas
> Objetivo: superar al original

- [ ] Paginación server-side en Angular (virtual scroll o botón "cargar más")
- [ ] Filtros y búsqueda en frontend
- [ ] Páginas de detalle (video con transcripción, artículo con contenido, repo con README)
- [ ] Settings page — formularios por fuente con validación reactiva (Angular Forms)
- [ ] Dashboard de estadísticas
- [ ] Sistema de favoritos
- [ ] Notificaciones toast (Angular Material Snackbar)

### Fase 5 — Calidad y Deploy
> Objetivo: código production-ready

- [ ] Tests unitarios backend (`pytest` + mocks de repos)
- [ ] Tests de integración (endpoints con DB de test)
- [ ] Tests de componentes Angular (`TestBed`)
- [ ] Dockerización (`docker-compose.yml` con backend + postgres + frontend)
- [ ] Variables de entorno bien separadas (`.env.dev`, `.env.prod`)
- [ ] Documentación OpenAPI revisada y completa

---

## 8. Variables de Entorno

### Backend (`.env`)
```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/newsradar

# YouTube
YOUTUBE_API_KEY=your_key_here

# GitHub
GITHUB_TOKEN=your_token_here        # ← Rate limit 5000 req/h vs 60 sin token

# Google News (no requiere key — RSS público)

# App
APP_ENV=development
APP_PORT=8000
CORS_ORIGINS=["http://localhost:4200"]

# Scheduler
SYNC_INTERVAL_MINUTES=60            # ← Configurable (no fijo como en el original)
```

### Frontend (`environment.ts`)
```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000/api'
};
```

---

## 9. Diferencias Clave vs Proyecto Original

| Aspecto | Original (Newsss) | v2 (NewsRadar) |
|---------|------------------|----------------|
| **Arquitectura** | Feature-based monolito Next.js | Separación clara Frontend/Backend |
| **Frontend** | Next.js SSR + React | Angular 19 SPA + standalone components |
| **Backend** | Next.js Server Actions | FastAPI REST API documentada |
| **DB** | SQLite (archivo local) | PostgreSQL (production-ready) |
| **ORM** | Prisma | SQLAlchemy 2.0 + Alembic |
| **State** | React Server Components | NgRx Signal Store |
| **HTTP Client** | `fetch` nativo | `httpx` async (backend) + `HttpClient` (frontend) |
| **Estilos** | Tailwind v4 + shadcn/ui | Tailwind v4 + Angular Material |
| **Validación** | TypeScript types | Pydantic v2 (backend) + Angular Validators (frontend) |
| **Paginación** | No (todo en memoria) | Server-side con cursor |
| **Tests** | Sin tests | pytest + Angular TestBed |
| **Deploy** | Local only | Docker Compose ready |

---

## 10. Naming Convention del Proyecto

- **Nombre del proyecto**: `NewsRadar`
- **Repositorio**: `newsradar/`
- **Backend**: `newsradar/backend/`
- **Frontend**: `newsradar/frontend/`

---

> [!IMPORTANT]
> Este documento es el plan maestro para pasar al agente de desarrollo. Empezar siempre por **Fase 1** (fundaciones del backend) antes de tocar el frontend.

> [!TIP]
> Para el GitHub pipeline, usar un **Personal Access Token** aumenta el rate limit de 60 a 5000 req/h — casi obligatorio para la fase de desarrollo.
