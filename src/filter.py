# -*- coding: utf-8 -*-
"""
Keyword-Filter fuer TechPulse.

Filtert Artikel nach konfigurierten Keywords per Word-Boundary-Regex
in Titel und Beschreibung. Titel-Matches zaehlen doppelt.

Autor: mmukex
"""

import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

from src.feed_parser import Article

# Modul-Logger, wird durch setup_logger() konfiguriert
logger = logging.getLogger("techpulse")

# Titel-Treffer zaehlen doppelt, weil ein Keyword im Titel
# deutlich relevanter ist als eins in der Beschreibung
TITLE_MATCH_WEIGHT = 2


def _build_word_boundary_pattern(keyword: str) -> str:
    """Regex-Pattern mit Word-Boundaries bauen.

    Damit matcht z.B. "AI" nicht in "MAIL".
    """
    return r'\b' + re.escape(keyword.lower()) + r'\b'


def keyword_matches(text: str, keywords: List[str]) -> List[str]:
    """
    Findet alle Keywords die im Text vorkommen.

    Args:
        text: Zu durchsuchender Text (Titel oder Beschreibung).
        keywords: Liste der Suchbegriffe.

    Returns:
        Gefundene Keywords, jedes maximal einmal.
    """
    if not text or not keywords:
        return []

    text_lower = text.lower()
    found_keywords: List[str] = []
    seen: Set[str] = set()

    for keyword in keywords:
        if keyword in seen:
            continue
        pattern = _build_word_boundary_pattern(keyword)

        if re.search(pattern, text_lower):
            found_keywords.append(keyword)
            seen.add(keyword)

    return found_keywords


def keyword_matches_with_positions(
    text: str,
    keywords: List[str]
) -> Dict[str, List[int]]:
    """Findet Keywords und ihre Start-Positionen im Text.

    Args:
        text: Zu durchsuchender Text.
        keywords: Liste der Suchbegriffe.

    Returns:
        Keyword -> Liste der Start-Positionen.
    """
    if not text or not keywords:
        return {}

    text_lower = text.lower()
    results: Dict[str, List[int]] = {}

    for keyword in keywords:
        pattern = _build_word_boundary_pattern(keyword)
        positions = [match.start() for match in re.finditer(pattern, text_lower)]

        if positions:
            results[keyword] = positions

    return results


def filter_articles(
    articles: List[Article],
    interests: List[Dict[str, Any]]
) -> List[Tuple[Article, List[str], str]]:
    """
    Filtert Artikel anhand der konfigurierten Interessen.

    Jeder Artikel wird gegen alle Interessen geprueft und dem
    mit den meisten Keyword-Treffern zugeordnet.

    Args:
        articles: Alle zu filternden Artikel.
        interests: Interessen-Konfigurationen mit 'name',
                  'keywords' und 'weight'.

    Returns:
        List von (Article, gefundene_keywords, interest_name).
    """
    logger.info(f"Filtere {len(articles)} Artikel mit {len(interests)} Interessen")

    filtered_results: List[Tuple[Article, List[str], str]] = []
    total_matches = 0

    for article in articles:
        best_match = _find_best_interest_match(article, interests)

        if best_match:
            _, all_keywords, interest_name = best_match
            filtered_results.append(best_match)
            total_matches += 1

            logger.debug(
                f"Match: '{article.title[:50]}...' -> {interest_name} "
                f"(Keywords: {', '.join(all_keywords)})"
            )

    logger.info(
        f"Filterung abgeschlossen: {total_matches} von {len(articles)} "
        f"Artikeln matchen mindestens ein Keyword"
    )

    return filtered_results


def _find_best_interest_match(
    article: Article,
    interests: List[Dict[str, Any]]
) -> Optional[Tuple[Article, List[str], str]]:
    """Findet das am besten passende Interesse fuer einen Artikel.

    Gibt (Article, alle_keywords, interest_name) zurueck,
    oder None wenn nichts matcht.
    """
    best_interest_name: str = ""
    best_match_count: int = 0
    # Sammelt Keywords ueber alle Interessen hinweg
    all_matched_keywords: Set[str] = set()

    for interest in interests:
        interest_name = interest['name']
        keywords = interest.get('keywords', [])

        # Titel und Beschreibung separat, weil Titel hoeher gewichtet
        title_matches = keyword_matches(article.title, keywords)
        desc_matches = keyword_matches(article.description, keywords)

        # Vereinigung: Keyword zaehlt auch wenn nur in einem Feld
        interest_matches = set(title_matches) | set(desc_matches)

        if interest_matches:
            all_matched_keywords.update(interest_matches)
            match_score = len(title_matches) * TITLE_MATCH_WEIGHT + len(desc_matches)

            # Artikel dem Interesse mit dem hoechsten Score zuordnen
            if match_score > best_match_count:
                best_match_count = match_score
                best_interest_name = interest_name

    if all_matched_keywords:
        return (article, list(all_matched_keywords), best_interest_name)

    return None


def filter_by_category(
    articles: List[Article],
    categories: List[str]
) -> List[Article]:
    """
    Filtert Artikel nach Feed-Kategorien.

    Args:
        articles: Zu filternde Artikel.
        categories: Erlaubte Kategorien (leer = alles durchlassen).

    Returns:
        Artikel die zu einer der Kategorien gehoeren.
    """
    # Leere Liste = kein Filter
    if not categories:
        return articles

    # Set fuer O(1)-Lookup beim Vergleich
    categories_lower = {cat.lower() for cat in categories}

    return [
        article for article in articles
        if article.category.lower() in categories_lower
    ]


def get_keyword_statistics(
    filtered_articles: List[Tuple[Article, List[str], str]]
) -> Dict[str, int]:
    """Zaehlt wie oft jedes Keyword vorkommt, sortiert nach Haeufigkeit."""
    keyword_counts: Counter[str] = Counter()

    for _, keywords, _ in filtered_articles:
        keyword_counts.update(keywords)

    return dict(keyword_counts.most_common())
