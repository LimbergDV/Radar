"""Tests del caso de uso de Google News.

Regresion principal: el id derivado del link debe caber siempre en VARCHAR(64),
porque el GUID original del RSS llega a ~800 caracteres y reventaba el INSERT.
"""

from datetime import datetime, timezone

from src.core.use_cases import sync_google_news as uc

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

def _entry(link: str, title: str = "Titulo", **extra) -> dict:
    entry = {
        "link": link,
        "title": title,
        "id": "CBMi" + "x" * 600,  # guid opaco gigante, como el real
        "published": "Sun, 05 Oct 2026 10:00:00 GMT",
        "source": {"title": "La Jornada", "href": "https://www.jornada.com.mx"},
    }
    entry.update(extra)
    return entry

def test_build_article_id_fits_in_varchar64():
    """El guid real de Google no cabe en 512; el id derivado si."""
    long_link = "https://news.google.com/rss/articles/" + "A" * 800 + "?oc=5"
    article_id = uc.build_article_id(long_link)
    assert len(article_id) == 40
    assert len(article_id) <= 64

def test_build_article_id_is_deterministic():
    link = "https://news.google.com/rss/articles/abc?oc=5"
    assert uc.build_article_id(link) == uc.build_article_id(link)

def test_build_article_id_differs_per_link():
    assert uc.build_article_id("https://a.com/1") != uc.build_article_id("https://a.com/2")

def test_build_rss_queries_single_language(sample_config_news):
    sample_config_news.ceid = "MX:es-419"
    queries = uc.build_rss_queries(sample_config_news)
    assert len(queries) == 1
    assert queries[0].language == "es"
    assert queries[0].ceid == "MX:es-419"

def test_build_rss_queries_dual_feed(sample_config_news):
    """Con varios ceid se generan consultas concurrentes (ES/EN), como el original."""
    queries = uc.build_rss_queries(sample_config_news)
    assert len(queries) == 2
    assert {q.language for q in queries} == {"es", "en"}
    assert {q.ceid for q in queries} == {"MX:es-419", "US:en"}

def test_build_rss_query_includes_filters(sample_config_news):
    sample_config_news.ceid = "MX:es-419"
    sample_config_news.site = "nature.com"
    sample_config_news.intitle = "AI"
    query = uc.build_rss_queries(sample_config_news)[0].query
    assert "site:nature.com" in query
    assert "intitle:AI" in query
    assert "when:1d" in query

def test_build_rss_queries_respects_max_results(sample_config_news):
    sample_config_news.max_results = 7
    queries = uc.build_rss_queries(sample_config_news)
    assert all(q.limit == 7 for q in queries)

def test_build_article_maps_all_fields():
    entry = _entry("https://news.google.com/rss/articles/tok1?oc=5", "Titulo real")
    article = uc.build_article(entry, "es", NOW)

    assert article is not None
    assert article.title == "Titulo real"
    assert article.source_name == "La Jornada"
    assert article.source_url == "https://www.jornada.com.mx"
    assert article.language == "es"
    assert article.pub_date == datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
    assert article.link == entry["link"]

def test_build_article_keeps_original_link_separately():
    """Guardamos el link opaco aparte para reintentar la decodificacion."""
    token_link = "https://news.google.com/rss/articles/tok9?oc=5"
    article = uc.build_article(_entry(token_link), "es", NOW)
    assert article.original_link == token_link
    assert article.link == token_link

def test_build_article_prefers_resolved_url():
    """Si se pudo resolver la URL real, esa es la que queda como link."""
    article = uc.build_article(
        _entry("https://news.google.com/rss/articles/tok2?oc=5"),
        "es",
        NOW,
        resolved_url="https://www.jornada.com.mx/noticia",
        content="Cuerpo del articulo",
        image_url="https://img.example/noticia.jpg",
    )
    assert article.link == "https://www.jornada.com.mx/noticia"
    assert article.original_link == "https://news.google.com/rss/articles/tok2?oc=5"
    assert article.content == "Cuerpo del articulo"
    assert article.image_url == "https://img.example/noticia.jpg"
    assert article.content_fetched is False

def test_build_article_returns_none_without_link():
    assert uc.build_article({"title": "Sin link"}, "es", NOW) is None

def test_build_article_returns_none_without_title():
    assert uc.build_article(_entry("https://x.com/1", title=""), "es", NOW) is None

def test_build_article_falls_back_to_fetched_at_on_bad_date():
    entry = _entry("https://x.com/1")
    entry["published"] = "no-es-una-fecha"
    article = uc.build_article(entry, "es", NOW)
    assert article.pub_date == NOW

def test_deduplicate_removes_same_link():
    link = "https://news.google.com/rss/articles/dup?oc=5"
    articles = [
        uc.build_article(_entry(link, "Uno"), "es", NOW),
        uc.build_article(_entry(link, "Uno otra vez"), "es", NOW),
    ]
    assert len(uc.deduplicate(articles)) == 1

def test_deduplicate_removes_same_title_across_languages():
    """El feed dual trae el mismo titular en es y en; nos quedamos con uno."""
    articles = [
        uc.build_article(_entry("https://n.com/a", "OpenAI lanza GPT-5"), "es", NOW),
        uc.build_article(_entry("https://n.com/b", "OpenAI lanza GPT-5"), "en", NOW),
    ]
    assert len(uc.deduplicate(articles)) == 1

def test_deduplicate_ignores_accents_when_comparing_titles():
    articles = [
        uc.build_article(_entry("https://n.com/a", "Inteligencia artificial:Boom"), "es", NOW),
        uc.build_article(_entry("https://n.com/b", "inteligencia artificial boom"), "en", NOW),
    ]
    assert len(uc.deduplicate(articles)) == 1

def test_deduplicate_keeps_distinct_articles():
    articles = [
        uc.build_article(_entry("https://n.com/a", "Titulo A"), "es", NOW),
        uc.build_article(_entry("https://n.com/b", "Titulo B"), "es", NOW),
    ]
    assert len(uc.deduplicate(articles)) == 2

def test_filter_by_window_keeps_today():
    entry = _entry("https://n.com/a")
    entry["published"] = "Sun, 05 Oct 2026 11:00:00 GMT"
    articles = [uc.build_article(entry, "es", NOW)]
    assert len(uc.filter_by_window(articles, 1, now=NOW)) == 1

def test_filter_by_window_drops_old_articles():
    """El filtro 'de ese dia': Google re-sirve articulos viejos, hay que quitarlos."""
    entry = _entry("https://n.com/a")
    entry["published"] = "Sun, 20 Sep 2026 11:00:00 GMT"  # 15 dias atras
    articles = [uc.build_article(entry, "es", NOW)]
    assert uc.filter_by_window(articles, 1, now=NOW) == []

def test_filter_by_window_zero_disables_filter():
    entry = _entry("https://n.com/a")
    entry["published"] = "Sun, 20 Sep 2026 11:00:00 GMT"
    articles = [uc.build_article(entry, "es", NOW)]
    assert len(uc.filter_by_window(articles, 0, now=NOW)) == 1

def test_should_fetch_content_false_for_google_link():
    """Las paginas splash de Google no contienen el articulo."""
    article = uc.build_article(_entry("https://news.google.com/rss/articles/x?oc=5"), "es", NOW)
    assert uc.should_fetch_content(article) is False

def test_should_fetch_content_true_for_publisher_url():
    article = uc.build_article(
        _entry("https://n.com/a"), "es", NOW, resolved_url="https://www.jornada.com.mx/x"
    )
    assert uc.should_fetch_content(article) is True