# Plan: Exponer NewsRadar a Agentes Externos

## Visión General

Convertir **NewsRadar** en una plataforma de datos abierta que permita a usuarios finales consumir toda la información disponible (YouTube, GitHub, noticias) a través de una API pública y usar **agentes externos** (Claude Code, ChatGPT, etc.) para **generar nuevas aplicaciones** sin modificar la app original.

**Flujo principal:**
```
Usuario + Prompt → Agente Externo → Consulta API NewsRadar → Genera Nueva App
```

---

## 1. Estado Actual (Baseline)

### Stack
- **Backend:** FastAPI + Python (async)
- **Frontend:** Angular
- **Base de datos:** PostgreSQL (Railway)
- **Deployment:** Railway (backend + DB)

### Endpoints Existentes
```
GET  /api/youtube/videos               → Videos paginados (lista)
GET  /api/youtube/videos/{video_id}    → Detalle + transcripción
POST /api/youtube/sync                 → Sincronización manual
GET  /api/youtube/config               → Config de búsqueda

GET  /api/news                         → Noticias paginadas
GET  /api/news/{article_id}            → Detalle de noticia
POST /api/news/sync                    → Sincronización manual
GET  /api/news/config                  → Config de filtros

GET  /api/github/repositories          → Repos paginados
GET  /api/github/repositories/{repo_id}→ Detalle del repo
POST /api/github/sync                  → Sincronización manual
GET  /api/github/config                → Config de búsqueda

GET  /api/                             → Feed agregado (YouTube + News + GitHub)
GET  /health                           → Health check
```

### Datos Disponibles
- **YouTube:** Videos, títulos, descripciones, transcripciones, canales
- **Google News:** Artículos, títulos, descripciones, URLs, fuentes
- **GitHub:** Repositorios, estrellas, lenguajes, descripción, URLs

---

## 2. Exposición de API para Agentes Externos

### 2.1 Crear Documentación OpenAPI Completa

**Estado actual:** FastAPI genera automáticamente docs en `/docs` y `/openapi.json`

**Acciones:**
1. ✅ Agregar ejemplos de respuesta en cada DTO
2. ✅ Documentar parámetros de filtro (language, limit, offset)
3. ✅ Exponer esquema en `/openapi.json` (ya está)
4. **NUEVO:** Crear archivo `API_GUIDE.md` con:
   - Descripción de cada endpoint
   - Ejemplos de curl/Python
   - Parámetros de filtro disponibles
   - Estructura de respuestas
   - Limitaciones (rate limit si aplica)

### 2.2 Crear Endpoint Agregado Mejorado

**Problema actual:** `/api/` puede estar limitado

**Solución:**
```python
# GET /api/search/all
# Parámetros:
#   - query: str (búsqueda en todos los orígenes)
#   - sources: str (youtube,news,github - separado por comas)
#   - limit: int (max 50)
#   - language: str (es, en)
#   - sort_by: str (relevance, date, stars)

Respuesta:
{
  "results": [
    {
      "type": "youtube|news|github",
      "id": "...",
      "title": "...",
      "source_url": "...",
      "description": "...",
      "metadata": {...}
    }
  ],
  "total": 42,
  "query": "...",
  "timestamp": "2026-10-16T..."
}
```

### 2.3 API Key / Autenticación Opcional

**Consideración:** ¿Necesitas rate limiting o acceso restringido?

**Por ahora (MVP):** Sin autenticación (API pública)
- Los agentes usan directamente los endpoints
- En futuro: agregar API Keys por usuario

---

## 3. Guía de Integración para Agentes Externos

### 3.1 Para Claude Code / ChatGPT

**Archivo:** `AGENT_INTEGRATION_GUIDE.md`

Contenido:
```markdown
# Cómo usar NewsRadar con Agentes de IA

## URL Base
https://newsradar-api.railway.app

## Autenticación
Ninguna requerida (API pública)

## Ejemplo: Generar Dashboard de YouTube + Noticias

### Paso 1: Consultar API
Prompt al agente:
"Obtén los últimos 10 videos de YouTube sobre IA y los últimos 5 artículos 
de noticias sobre IA. Luego genera una aplicación web que los muestre."

### Paso 2: El agente ejecuta
GET https://newsradar-api.railway.app/api/youtube/videos?limit=10&language=es
GET https://newsradar-api.railway.app/api/news?limit=5

### Paso 3: El agente genera
- HTML/CSS/JS
- React app
- Aplicación standalone
```

### 3.2 Casos de Uso Específicos

#### Caso 1: Dashboard de IA + GitHub
```
Usuario dice: "Crea un dashboard que muestre noticias sobre IA, 
videos en YouTube sobre IA y repos trending en GitHub. Hazlo responsive."

Agente:
1. GET /api/news?q=IA
2. GET /api/youtube/videos?q=IA
3. GET /api/github/repositories?q=IA
4. Genera app React con gráficos, filtros, búsqueda
5. Entrega código o deploy en Vercel
```

#### Caso 2: Newsletter Automática
```
Usuario: "Crea un script que cada mañana envíe un email con 
los mejores repos, videos y noticias de la semana sobre LLMs"

Agente:
1. GET /api/search/all?query=LLMs&sort_by=date
2. Genera Python script con APScheduler + SendGrid
3. User la guarda en su servidor / cron job
```

#### Caso 3: App de Comparación de Fuentes
```
Usuario: "Muestra el mismo tema desde 3 ángulos: video de YouTube,
artículo de noticia, discussión en GitHub issues."

Agente:
1. GET /api/search/all?query=topic&sources=youtube,news,github
2. Agrupa por tema
3. Genera app interactiva con pestañas
```

---

## 4. Filtrado y Precisión de Datos

### 4.1 Advertencia sobre Datos Inexactos

**Problema:** A veces sale "horóscopo" al filtrar por "Gemini" (modelo IA)

**Solución:**
1. **En la app actual:** Mejorar filtros en el backend
2. **Para agentes:** Documentar limitación
3. **Crear endpoint de "feedback":** Permitir reportar datos inexactos

```python
# POST /api/report/inaccuracy
{
  "source_type": "youtube|news|github",
  "source_id": "...",
  "reason": "contenido_irrelevante | spam | otro",
  "comment": "Esto no es sobre IA, es astrología"
}
```

### 4.2 Validación en Agentes

**Documentar en AGENT_INTEGRATION_GUIDE.md:**
```markdown
## Validación de Datos

Recomendaciones al usar NewsRadar:
1. Validar que el contenido sea relevante a la búsqueda
2. Usar múltiples fuentes (no confiar en una sola)
3. Verificar URLs antes de presentar al usuario
4. Si hay contenido spam/irrelevante, reportarlo vía POST /api/report/inaccuracy
```

---

## 5. Archivos de Documentación a Crear

### 5.1 `API_GUIDE.md` (Referencia técnica)
```
- Endpoints completos
- Parámetros
- Ejemplos curl/Python
- Estructura de respuestas
- Códigos de error
- Limitaciones actuales
```

### 5.2 `AGENT_INTEGRATION_GUIDE.md` (Para usuarios + agentes)
```
- Cómo conectar con la API
- Casos de uso ejemplos
- Validación de datos
- Limitaciones conocidas
- Reporte de problemas
```

### 5.3 `DEPLOYMENT_GUIDE.md` (Para que usuarios desplieguen apps generadas)
```
- Deploy en Vercel (frontend)
- Deploy en Railway (backend Python)
- Deploy en Replit (scripts)
- Variables de entorno necesarias
```

---

## 6. Arquitectura de Uso: Agente Externo

```
┌─────────────────────────────────────────────────────────┐
│ Usuario en Claude Code / ChatGPT                        │
│                                                         │
│ "Crea una app web con los últimos videos de IA"       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
        ┌────────────────────────┐
        │   Agente (Claude/GPT)  │
        │                        │
        │  1. Lee guía de API    │
        │  2. Consulta endpoints │
        │  3. Procesa JSON       │
        │  4. Genera código      │
        │  5. Entrega archivos   │
        └────────┬───────────────┘
                 │
                 ↓
    ┌────────────────────────────┐
    │  NewsRadar API (Railway)   │
    │  - /api/youtube/videos     │
    │  - /api/news               │
    │  - /api/github/repositories│
    └────────────────────────────┘
                 │
                 ↓
        ┌────────────────────┐
        │   PostgreSQL       │
        │   (Railway)        │
        └────────────────────┘
                 │
                 ↓
    ┌────────────────────────────┐
    │  Usuario descarga código   │
    │  y lo despliega en Vercel  │
    │  (o donde quiera)          │
    └────────────────────────────┘
```

---

## 7. Roadmap de Implementación

### Fase 1: MVP (Semana 1-2)
- [ ] Crear `API_GUIDE.md` con todos los endpoints actuales
- [ ] Crear `AGENT_INTEGRATION_GUIDE.md` con casos de uso
- [ ] Verificar que `/openapi.json` está expuesto correctamente
- [ ] Crear endpoint agregado `/api/search/all` (opcional pero útil)
- [ ] Testear con un agente (Claude Code) manualmente

### Fase 2: Mejora de Datos (Semana 2-3)
- [ ] Implementar `/api/report/inaccuracy` para feedback
- [ ] Mejorar filtros en backend para reducir falsos positivos
- [ ] Documentar limitaciones conocidas

### Fase 3: Documentación Extra (Semana 3-4)
- [ ] Crear `DEPLOYMENT_GUIDE.md` para apps generadas
- [ ] Agregar ejemplos de código en múltiples lenguajes
- [ ] Video tutorial (opcional)

### Fase 4: Escala (Futuro)
- [ ] Rate limiting si se necesita
- [ ] API Keys para control
- [ ] Dashboard de uso
- [ ] Webhook para sincronización en tiempo real

---

## 8. Seguridad y Consideraciones

### 8.1 Datos Públicos
✅ Todos los datos de NewsRadar son públicos (YouTube, News, GitHub)
→ No hay problema de seguridad con exposición pública

### 8.2 CORS
✅ Ya está configurado en FastAPI
```python
CORSMiddleware(
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 8.3 Rate Limiting (Futuro)
- Considerar agregar si hay abuso
- Por ahora: confiar en que agentes no harán spam

### 8.4 Privacidad del Usuario
- Los agentes generarán código que el usuario controla
- El usuario decide si comparte esas apps con otros
- NewsRadar no almacena código generado por agentes

---

## 9. Métricas de Éxito

1. ✅ API documentada y accesible
2. ✅ Agente externo (ej: Claude Code) puede consumir datos sin errors
3. ✅ Agente puede generar app funcional en <5 minutos
4. ✅ Usuario puede desplegar app generada sin modificaciones
5. ✅ Mínimo 1 caso de uso validado (YouTube + News)

---

## 10. Preguntas Pendientes (Para Aclarar)

1. ¿Quieres que los agentes puedan disparar sincronización manual (`POST /sync`)?
   - Por ahora: NO (solo lectura)
   - Futuro: Sí, con autenticación

2. ¿Límite de resultados?
   - Por ahora: 50 máximo
   - Futuro: Configurable

3. ¿Análisis de datos?
   - Agregar estadísticas: trending topics, videos más vistos, etc.
   - Útil para dashboards

---

## 11. Estructura de Respuesta: Ejemplo Unificado

```json
{
  "results": [
    {
      "id": "unique_id",
      "type": "youtube|news|github",
      "title": "Nuevo Model de OpenAI GPT-5",
      "description": "OpenAI lanza GPT-5 con capacidades...",
      "url": "https://youtube.com/watch?v=...",
      "source": {
        "name": "YouTube | BBC News | GitHub",
        "icon": "youtube | news | github"
      },
      "metadata": {
        "views": 1200,
        "published_at": "2026-10-15T10:30:00Z",
        "language": "es",
        "channel": "AI Explained" // solo YouTube
        "author": "Tech News Daily" // solo News
        "stars": 2500 // solo GitHub
      },
      "relevance_score": 0.95
    }
  ],
  "pagination": {
    "total": 142,
    "limit": 10,
    "offset": 0,
    "has_next": true
  },
  "query": {
    "search_term": "GPT-5",
    "sources": ["youtube", "news", "github"],
    "language": "es"
  },
  "timestamp": "2026-10-16T14:30:00Z"
}
```

---

## Siguiente Paso

**Decide:**
1. ¿Empezamos por crear la documentación (API_GUIDE.md)?
2. ¿Mejoramos primero el endpoint agregado `/api/search/all`?
3. ¿Testamos primero con Claude Code manualmente?

**Mi recomendación:** Empezar con **documentación** (rápido) → **testar con agente** → **mejorar según feedback**.
