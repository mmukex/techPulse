# -*- coding: utf-8 -*-
"""
HTML-Report-Generator fuer TechPulse.

Bereitet die Artikel-Daten auf und rendert sie per Jinja2
in ein HTML-Template.

Autor: mmukex
"""

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from src.feed_parser import Article
from src.scorer import SCORE_LEVEL_LOW_THRESHOLD, SCORE_LEVEL_HIGH_THRESHOLD

logger = logging.getLogger("techpulse")


def prepare_template_data(
    scored_articles: List[Tuple[Article, float, str]],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Bereitet die Artikel-Daten fuers Jinja2-Template auf.

    Args:
        scored_articles: Bewertete Artikel als (Article, score, interest_name).
        config: Anwendungskonfiguration fuer Metadaten im Report.

    Returns:
        Dict mit articles, categories, interests, statistics,
        generated_at und config fuer das Template.
    """
    logger.info("Bereite Template-Daten auf")

    # Dataclass-Objekte in Dicts umwandeln fuers Template
    articles_data = [
        _article_to_dict(article, score, interest_name)
        for article, score, interest_name in scored_articles
    ]

    # Gruppierungen fuer verschiedene Ansichten im Report
    categories = _group_articles_by(articles_data, 'category', default='Sonstige')
    interests = _group_articles_by(articles_data, 'interest', default='Allgemein')
    statistics = _calculate_statistics(articles_data)

    template_data = {
        'articles': articles_data,
        'categories': categories,
        'interests': interests,
        'statistics': statistics,
        'generated_at': datetime.now(),
        # Nur relevante Config-Werte ans Template geben
        'config': {
            'feeds_count': len(config.get('feeds', [])),
            'interests_count': len(config.get('interests', [])),
            'min_score': config.get('output', {}).get('min_score', 0)
        }
    }

    logger.debug(f"Template-Daten aufbereitet: {statistics}")

    return template_data


def _article_to_dict(
    article: Article,
    score: float,
    interest_name: str
) -> Dict[str, Any]:
    """Article-Objekt in ein flaches Dict fuers Template konvertieren."""
    return {
        'title': article.title,
        'link': article.link,
        'description': article.description,
        'published': article.published,
        'feed_name': article.feed_name,
        'category': article.category,
        'author': article.author,
        'score': score,
        'interest': interest_name,
        'score_level': _get_score_level(score),
        'source_priority': article.source_priority
    }


def _get_score_level(score: float) -> str:
    """Score in 'low'/'medium'/'high' einordnen (fuer CSS-Klassen)."""
    if score < SCORE_LEVEL_LOW_THRESHOLD:
        return 'low'
    elif score < SCORE_LEVEL_HIGH_THRESHOLD:
        return 'medium'
    else:
        return 'high'


def _group_articles_by(
    articles: List[Dict[str, Any]],
    key: str,
    default: str = "Sonstige"
) -> Dict[str, List[Dict]]:
    """Gruppiert Artikel nach einem Dict-Schluessel (z.B. 'category')."""
    groups: Dict[str, List[Dict]] = defaultdict(list)

    for article in articles:
        group_name = article.get(key, default)
        groups[group_name].append(article)

    return dict(groups)


def _calculate_statistics(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregierte Statistiken fuer den Report-Header berechnen."""
    # Leere Liste -> Null-Werte statt Division-by-Zero
    if not articles:
        return {
            'total_articles': 0,
            'avg_score': 0,
            'max_score': 0,
            'min_score': 0,
            'categories_count': 0,
            'interests_count': 0
        }

    scores = [a['score'] for a in articles]
    categories = set(a['category'] for a in articles)
    interests = set(a['interest'] for a in articles)

    return {
        'total_articles': len(articles),
        'avg_score': sum(scores) / len(scores),
        'max_score': max(scores),
        'min_score': min(scores),
        'categories_count': len(categories),
        'interests_count': len(interests)
    }


def generate_html_report(
    scored_articles: List[Tuple[Article, float, str]],
    config: Dict[str, Any],
    template_dir: str = "templates"
) -> str:
    """
    Generiert den HTML-Report.

    Args:
        scored_articles: Bewertete Artikel.
        config: Anwendungskonfiguration.
        template_dir: Verzeichnis mit Jinja2-Templates.

    Returns:
        Fertig gerenderter HTML-String.

    Raises:
        TemplateNotFound: Wenn report_template.html fehlt.
    """
    logger.info("Generiere HTML-Report")

    template_data = prepare_template_data(scored_articles, config)

    try:
        # autoescape gegen XSS in Artikeltiteln/-beschreibungen
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )

        # Custom Filter fuer Datums- und Score-Formatierung
        env.filters['format_date'] = _format_date_filter
        env.filters['format_score'] = _format_score_filter

        template = env.get_template('report_template.html')
        html_content = template.render(**template_data)

        logger.info(f"HTML-Report generiert ({len(html_content)} Zeichen)")
        return html_content

    except TemplateNotFound as e:
        logger.error(f"Template nicht gefunden: {e}")
        raise
    except Exception as e:
        logger.error(f"Fehler bei der Report-Generierung: {e}")
        raise


def _format_date_filter(
    value: Optional[datetime],
    format_str: str = "%d.%m.%Y %H:%M"
) -> str:
    """Jinja2-Filter: datetime -> formatierter String, oder 'Unbekannt'."""
    if value is None:
        return "Unbekannt"
    return value.strftime(format_str)


def _format_score_filter(value: float, decimals: int = 1) -> str:
    """Jinja2-Filter: Score auf n Dezimalstellen formatieren."""
    return f"{value:.{decimals}f}"


def save_report(
    html_content: str,
    output_dir: str,
    filename_prefix: str = "techpulse_report"
) -> str:
    """
    Speichert den HTML-Report als Datei.

    Args:
        html_content: Generierter HTML-String.
        output_dir: Zielverzeichnis.
        filename_prefix: Praefix fuer den Dateinamen.

    Returns:
        Absoluter Pfad zur gespeicherten Datei.

    Raises:
        PermissionError: Wenn Verzeichnis nicht beschreibbar.
        IOError: Bei sonstigen Dateisystem-Fehlern.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Zeitstempel im Dateinamen damit nichts ueberschrieben wird
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp}.html"
    filepath = output_path / filename

    try:
        filepath.write_text(html_content, encoding='utf-8')
        logger.info(f"Report gespeichert: {filepath}")
        return str(filepath.absolute())

    except IOError as e:
        logger.error(f"Fehler beim Speichern des Reports: {e}")
        raise


def get_latest_report(output_dir: str) -> Optional[str]:
    """Neuesten Report im Output-Verzeichnis finden (nach Aenderungsdatum)."""
    output_path = Path(output_dir)

    if not output_path.exists():
        return None

    html_files = list(output_path.glob("*.html"))

    if not html_files:
        return None

    # Nach mtime statt Dateiname, falls der Zeitstempel mal abweicht
    latest = max(html_files, key=lambda f: f.stat().st_mtime)

    return str(latest.absolute())
