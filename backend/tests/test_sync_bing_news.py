"""Tests del discovery de noticias vía Bing News RSS.

Regresión que cubre: el enlace de Bing es un wrapper `apiclick.aspx` con la URL
del medio escondida en `url=`. Si no se desempaqueta, trafilatura no tiene qué
descargar y el articulo se guarda sin cuerpo (que era exactamente el sintoma
que reportaba la UI).
"""

from src.core.entities.config import GoogleNewsConfig
from src.core.use_cases import sync_bing_news as uc
from src.infrastructure.external.bing_news_api import _normalize_entry

APPCLICK = (
    "http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&tid=abc"
    "&url=https%3a%2f%2fwww.eleconomista.com.mx%2ftecnologia%2fnoticia-123"
    "&c=1&mkt=es-mx"
)

def test_decode_publisher_url_unwraps_apiclick():
    assert uc.decode_publisher_url(APPCLICK) == (
        "https://www.eleconomista.com.mx/tecnologia/noticia-123"
    )

def test_decode_publisher_url_passes_through_direct_link():
    url = "https://elpais.com/tecologia/2026-10-08/noticia.html"
    assert uc.decode_publisher_url(url) == url

def test_decode_publisher_url_handles_empty():
    assert uc.decode_publisher_url("") == ""

def test_decode_publisher_url_keeps_link_when_wrapper_has_no_url():
    """Si el wrapper llega sin `url`, mejor el original que perder el articulo."""
    link = "http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid="
    assert uc.decode_publisher_url(link) == link

def test_split_query_terms_splits_on_or():
    assert uc.split_query_terms("Inteligencia Artificial OR IA") == [
        "Inteligencia Artificial", "IA",
    ]

def test_split_query_terms_is_case_insensitive():
    assert uc.split_query_terms("IA or ChatGPT or gemini") == ["IA", "ChatGPT", "gemini"]

def test_split_query_terms_dedupes_and_keeps_single_term():
    assert uc.split_query_terms("IA or ia") == ["IA"]
    assert uc.split_query_terms("solo una") == ["solo una"]

def test_split_query_terms_empty_query():
    assert uc.split_query_terms("") == []
    assert uc.split_query_terms("   ") == []

def test_build_bing_queries_expands_terms_and_markets():
    """Sin esto, un OR de Bing no filtra y el pool de articulos se hunde."""
    config = GoogleNewsConfig(
        q="Inteligencia Artificial OR IA", ceid="MX:es-419,US:en", max_results=10,
    )
    queries = uc.build_bing_queries(config)

    assert len(queries) == 4  # 2 terminos x 2 mercados
    assert {q.setmkt for q in queries} == {"es-MX", "en-US"}
    assert {q.query for q in queries} == {"Inteligencia Artificial", "IA"}
    assert all(q.limit == 10 for q in queries)

def test_build_bing_queries_single_market_defaults():
    config = GoogleNewsConfig(q="IA", hl="es-419", gl="MX", ceid="MX:es-419")
    queries = uc.build_bing_queries(config)
    assert len(queries) == 1
    assert queries[0].setmkt == "es-MX"
    assert queries[0].language == "es"

def test_build_bing_queries_appends_site_and_intitle():
    config = GoogleNewsConfig(q="IA", ceid="MX:es-419", site="elpais.com", intitle="inteligencia")
    query = uc.build_bing_queries(config)[0].query
    assert "site:elpais.com" in query
    assert "intitle:inteligencia" in query

def test_build_bing_queries_never_returns_empty():
    """Sin consultas no hay nada que pedir y el feed quedaria vacio."""
    queries = uc.build_bing_queries(GoogleNewsConfig(q="", ceid="MX:es-419"))
    assert len(queries) == 1

def test_normalize_entry_sets_real_link_and_source():
    entry = _normalize_entry({"title": "Titulo", "link": APPCLICK, "published": "Thu, 08 Oct 2026 10:00:00 GMT"})
    assert entry is not None
    assert entry["link"] == "https://www.eleconomista.com.mx/tecnologia/noticia-123"
    # El RSS de Bing no trae `source` y sin el medio no se muestra en la UI.
    assert entry["source"]["title"] == "eleconomista.com.mx"
    assert entry["original_link"] == APPCLICK

def test_normalize_entry_drops_entry_without_link():
    assert _normalize_entry({"title": "Sin link"}) is None

def test_has_real_publisher_link():
    assert uc.has_real_publisher_link("https://elpais.com/x") is True
    assert uc.has_real_publisher_link(APPCLICK) is False