"""Tests del fallback de transcripciones (RapidAPI).

Cubre justo lo que no se puede probar contra el proveedor real sin gastar
cuota: el parseo de la respuesta, el motivo del fallo y, sobre todo, los dos
frenos de gasto —el tope mensual de la app y el contador que reporta el propio
proveedor—.

La cuota del plan free son ~100 peticiones al mes: un bug aquí se paga en
silencio dejando al feed sin transcripciones hasta el mes siguiente.
"""

import httpx
import pytest

from src.core.use_cases.sync_youtube import pick_transcript_language
from src.infrastructure.database.settings import settings
from src.infrastructure.external import rapidapi_transcript as rapid
from src.infrastructure.external import youtube_api


@pytest.fixture(autouse=True)
def _clean_provider(monkeypatch):
    """Key configurada y contador a cero en cada test.

    El contador es estado de módulo a propósito (sobrevive entre peticiones
    dentro del mismo proceso), así que sin reiniciarlo un test contaminaría al
    siguiente.
    """
    monkeypatch.setattr(settings, "rapidapi_key", "test-key", raising=False)
    monkeypatch.setattr(settings, "rapidapi_transcript_budget", 100, raising=False)
    monkeypatch.setattr(rapid, "_budget", rapid._Budget(), raising=False)
    yield
    rapid._transport = None


def use_provider(handler) -> None:
    rapid._transport = httpx.MockTransport(handler)


def ok(text: str, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(200, headers=headers, json={"success": True, "transcript": text})


class TestRapidApiFetch:
    async def test_parses_text_and_unescapes_html(self):
        def handler(request):
            assert request.url.params["videoId"] == "v1"
            assert request.url.params["flat_text"] == "true"
            assert request.headers["x-rapidapi-host"] == settings.rapidapi_host
            return ok("hola &gt;&gt; mundo\n\n  otra   frase")

        use_provider(handler)
        text, error = await rapid.fetch_transcript("v1")

        assert error is None
        assert text == "hola >> mundo otra frase"

    async def test_sends_the_language_when_given(self):
        """Sin `lang` el proveedor devuelve una pista arbitraria (nos pasó: árabe)."""

        def handler(request):
            assert request.url.params["lang"] == "es"
            return ok("texto")

        use_provider(handler)
        text, error = await rapid.fetch_transcript("v1", lang="es")

        assert (text, error) == ("texto", None)

    async def test_omits_lang_when_unknown(self):
        def handler(request):
            assert "lang" not in request.url.params
            return ok("texto")

        use_provider(handler)
        await rapid.fetch_transcript("v1", lang=None)

    async def test_accepts_a_list_of_segments(self):
        """Por si el proveedor ignora `flat_text` y devuelve los fragmentos."""

        def handler(request):
            return httpx.Response(
                200,
                json={"success": True, "transcript": [{"text": "uno"}, {"text": "dos"}]},
            )

        use_provider(handler)
        text, error = await rapid.fetch_transcript("v1")

        assert error is None
        assert text == "uno dos"

    async def test_video_without_transcript_is_not_an_error(self):
        """El proveedor responde 200 con `success: false`: simplemente no hay."""

        def handler(request):
            return httpx.Response(200, json={"success": False, "error": "not available"})

        use_provider(handler)
        text, error = await rapid.fetch_transcript("v1")

        assert text is None
        assert error == "sin_transcripcion"

    async def test_reports_rate_limit_and_stops_calling(self):
        calls: list[str] = []

        def handler(request):
            calls.append(request.url.params["videoId"])
            return ok("texto", headers={"x-ratelimit-requests-remaining": "0"})

        use_provider(handler)

        first_text, first_error = await rapid.fetch_transcript("v1")
        second_text, second_error = await rapid.fetch_transcript("v2")

        assert (first_text, first_error) == ("texto", None)
        # El header dice que no queda nada: la segunda ni se intenta.
        assert (second_text, second_error) == (None, "cuota_agotada")
        assert calls == ["v1"]

    async def test_respects_the_app_budget(self, monkeypatch):
        monkeypatch.setattr(settings, "rapidapi_transcript_budget", 1)
        use_provider(lambda request: ok("texto"))

        await rapid.fetch_transcript("v1")
        text, error = await rapid.fetch_transcript("v2")

        assert text is None
        assert error == "cuota_agotada"

    async def test_http_429_is_reported_as_quota(self):
        use_provider(lambda request: httpx.Response(429, json={"message": "too many"}))

        text, error = await rapid.fetch_transcript("v1")

        assert text is None
        assert error == "http_429"

    async def test_without_key_it_does_not_spend_anything(self, monkeypatch):
        monkeypatch.setattr(settings, "rapidapi_key", "")

        def handler(request):
            raise AssertionError("sin key no debe salir ninguna petición")

        use_provider(handler)
        text, error = await rapid.fetch_transcript("v1")

        assert (text, error) == (None, "sin_api_key")

    async def test_budget_status_exposes_the_provider_counter(self):
        use_provider(lambda request: ok("x", headers={"x-ratelimit-requests-remaining": "7"}))

        await rapid.fetch_transcript("v1")
        status = rapid.budget_status()

        assert status["enabled"] is True
        assert status["used_by_app"] == 1
        assert status["remaining"] == 7


class TestResolveTranscript:
    """El orden importa: la vía gratuita primero, el fallback solo si falla."""

    async def test_free_source_is_tried_first(self, monkeypatch):
        monkeypatch.setattr(
            youtube_api, "fetch_transcript", lambda video_id, languages: ("texto gratis", None)
        )

        async def must_not_be_called(video_id, lang=None):
            raise AssertionError("no debe gastarse cuota si la vía gratuita funciona")

        monkeypatch.setattr(youtube_api.rapidapi_transcript, "fetch_transcript", must_not_be_called)

        text, error, source = await youtube_api.resolve_transcript("v1", ["es"])

        assert (text, error, source) == ("texto gratis", None, youtube_api.FREE_TRANSCRIPT_SOURCE)

    async def test_falls_back_when_youtube_blocks_the_ip(self, monkeypatch):
        """IpBlocked es el caso real en Railway: ahí entra RapidAPI."""
        seen: dict = {}

        def blocked(video_id, languages):
            return (youtube_api.NO_TRANSCRIPT, "IpBlocked")

        async def paid(video_id, lang=None):
            seen["lang"] = lang
            return ("texto del fallback", None)

        monkeypatch.setattr(youtube_api, "fetch_transcript", blocked)
        monkeypatch.setattr(youtube_api.rapidapi_transcript, "fetch_transcript", paid)

        text, error, source = await youtube_api.resolve_transcript("v1", ["es", "en"], "en-US")

        assert (text, error, source) == (
            "texto del fallback",
            None,
            youtube_api.RAPIDAPI_TRANSCRIPT_SOURCE,
        )
        # Se normaliza 'en-US' -> 'en' antes de pedirlo.
        assert seen["lang"] == "en"

    async def test_keeps_both_reasons_when_everything_fails(self, monkeypatch):
        monkeypatch.setattr(
            youtube_api, "fetch_transcript", lambda video_id, languages: ("Transcripción no disponible", "IpBlocked")
        )

        async def no_budget(video_id, lang=None):
            return (None, "cuota_agotada")

        monkeypatch.setattr(youtube_api.rapidapi_transcript, "fetch_transcript", no_budget)

        text, error, source = await youtube_api.resolve_transcript("v1", ["es"])

        assert text == youtube_api.NO_TRANSCRIPT
        assert error == "IpBlocked/cuota_agotada"
        assert source == ""

    async def test_a_genuine_missing_transcript_stays_simple(self, monkeypatch):
        """Si el video no tiene subtítulos, repetir 'sin_transcripcion' no aporta."""
        monkeypatch.setattr(
            youtube_api, "fetch_transcript", lambda video_id, languages: ("Transcripción no disponible", "NoTranscriptFound")
        )

        async def no_transcript(video_id, lang=None):
            return (None, "sin_transcripcion")

        monkeypatch.setattr(youtube_api.rapidapi_transcript, "fetch_transcript", no_transcript)

        _text, error, _source = await youtube_api.resolve_transcript("v1", ["es"])

        assert error == "NoTranscriptFound"


class TestPickTranscriptLanguage:
    """El idioma que se le manda al fallback: si no coincide, el texto no sirve."""

    def test_prefers_the_declared_language(self):
        assert pick_transcript_language("es-419", ["es", "en"]) == "es"

    def test_uses_the_declared_language_when_nothing_is_configured(self):
        assert pick_transcript_language("en", []) == "en"

    def test_falls_back_to_the_first_configured_language(self):
        # 'ja' no está configurado: mejor pedir 'es' que dejar que el proveedor
        # elija una pista cualquiera.
        assert pick_transcript_language("ja", ["es", "en"]) == "es"

    def test_handles_a_video_without_declared_language(self):
        assert pick_transcript_language(None, ["en", "es"]) == "en"

    def test_returns_none_without_any_language(self):
        assert pick_transcript_language(None, []) is None
