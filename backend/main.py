from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.infrastructure.database.settings import settings

# 1. Agrega esta importación
from src.presentation.routers import youtube_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Radar API iniciando...")
    yield
    print("🛑 Radar API apagándose...")

app = FastAPI(
    title="Radar API",
    description="Agregador de noticias sobre IA — Angular + FastAPI",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Agrega el router de YouTube
app.include_router(youtube_router.router, prefix="/api/youtube", tags=["YouTube"])

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "env": settings.app_env}