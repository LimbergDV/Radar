"""Cliente de la API REST de GitHub.

Sin token el limite es 60 req/h (insuficiente: la busqueda + los READMEs se
comen el cupo rapido), asi que `settings.github_token` sube el limite a 5000.
"""

import asyncio
import base64
from datetime import datetime, timezone

import httpx

from src.core.entities.config import GitHubConfig
from src.core.entities.github import GitHubRepo
from src.core.logging_config import get_logger
from src.core.use_cases import sync_github as uc

logger = get_logger(__name__)

BASE_URL = "https://api.github.com"
REQUEST_TIMEOUT = 30.0
SEARCH_MAX_RESULTS = 100  # tope por pagina de la API
MAX_README_CONCURRENCY = 6


class GitHubFetcher:
    def __init__(self, token: str = ""):
        self.token = token
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "NewsRadar/1.0",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers=self._headers,
            follow_redirects=True,
        )

    async def search_repos(self, config: GitHubConfig) -> list[dict]:
        """Busca repos segun los filtros de la configuracion."""
        query = uc.build_search_query(config)
        logger.info("GitHub search: %s", query)

        try:
            async with self._client() as client:
                response = await client.get(
                    f"{BASE_URL}/search/repositories",
                    params={
                        "q": query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": min(config.max_results, SEARCH_MAX_RESULTS),
                    },
                )
        except httpx.HTTPError as exc:
            logger.error("Error de red en GitHub search: %s", exc)
            return []

        if response.status_code == 403 and "rate limit" in response.text.lower():
            logger.error(
                "GitHub devuelve 403 (rate limit). Configura GITHUB_TOKEN en .env "
                "para subir de 60 a 5000 req/h."
            )
            return []

        if response.status_code != 200:
            logger.error("GitHub search devolvio %s: %s", response.status_code, response.text[:200])
            return []

        items = response.json().get("items", [])
        logger.info("GitHub: %d repos crudos", len(items))
        return items

    async def fetch_readme(self, client: httpx.AsyncClient, repo: dict) -> str:
        """Descarga el README (base64) de un repo. Vacio si no hay."""
        full_name = repo.get("full_name")
        if not full_name:
            return ""

        try:
            response = await client.get(f"{BASE_URL}/repos/{full_name}/readme")
            if response.status_code != 200:
                return ""
            payload = response.json()
            if payload.get("encoding") != "base64" or not payload.get("content"):
                return ""
            return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            logger.debug("Sin README para %s: %s", full_name, exc)
            return ""

    async def fetch_readmes(self, repos: list[dict]) -> dict[str, str]:
        """READMEs de varios repos en paralelo, acotados por semaforo."""
        semaphore = asyncio.Semaphore(MAX_README_CONCURRENCY)
        results: dict[str, str] = {}

        async def one(client: httpx.AsyncClient, repo: dict) -> tuple[str, str]:
            async with semaphore:
                full_name = repo.get("full_name", "")
                return full_name, await self.fetch_readme(client, repo)

        async with self._client() as client:
            for full_name, readme in await asyncio.gather(*(one(client, r) for r in repos)):
                if readme:
                    results[full_name] = readme

        logger.info("GitHub: %d/%d READMEs descargados", len(results), len(repos))
        return results

    async def sync_pipeline(self, config: GitHubConfig) -> list[GitHubRepo]:
        """Busca, filtra en local, descarga READMEs y devuelve entidades."""
        raw_repos = await self.search_repos(config)
        if not raw_repos:
            return []

        # La query de GitHub usa OR entre keywords, asi que revalidamos los
        # umbrales en local.
        matching = [repo for repo in raw_repos if uc.matches_filters(repo, config)]
        if len(matching) != len(raw_repos):
            logger.info(
                "GitHub: %d repos descartados por filtros locales (min %d stars, %d forks)",
                len(raw_repos) - len(matching),
                config.min_stars,
                config.min_forks,
            )

        if not matching:
            return []

        readmes = await self.fetch_readmes(matching)
        synced_at = datetime.now(timezone.utc)

        repos = [
            uc.build_repo(repo, readmes.get(repo.get("full_name", ""), ""), synced_at)
            for repo in matching
        ]

        repos = uc.dedupe(repos)
        return uc.rank(repos, config.max_results)