# -*- coding: utf-8 -*-
"""
Scoring-Modul fuer TechPulse.

Bewertet die Relevanz von Artikeln anhand von Keyword-Matches,
deren Position (Titel vs. Beschreibung), Interessen-Gewichtung
und Quellenpriorität.

Formel: base = (desc_matches * weight) + (title_matches * 1.5 * weight)
        final = base * source_priority

Autor: mmukex
"""

import logging
from typing import Any, Dict, List, Tuple

from src.feed_parser import Article
from src.filter import keyword_matches

logger = logging.getLogger("techpulse")

# Keywords im Titel sind ein wichtiger Relevanz-Indikator
TITLE_MULTIPLIER = 1.5
# Skalierungsfaktor pro Match
BASE_SCORE_PER_MATCH = 1.0

# Schwellwerte fuer die Farbcodierung im Report
SCORE_LEVEL_LOW_THRESHOLD = 3.0
SCORE_LEVEL_HIGH_THRESHOLD = 6.0

# Bereichsgrenzen fuer die Verteilungsanalyse
DISTRIBUTION_BOUNDARIES = [2, 4, 6, 8]


def _compute_score_breakdown(
    article: Article,
    keywords: List[str],
    weight: float
) -> Dict[str, Any]:
    """Zentrale Scoring-Logik, wird von calculate_score()
    und calculate_detailed_score() gemeinsam genutzt.
    """
    title_matches = keyword_matches(article.title, keywords)
    description_matches = keyword_matches(
        article.description, keywords
    )

    title_score = (len(title_matches) * TITLE_MULTIPLIER
                   * weight * BASE_SCORE_PER_MATCH)
    description_score = (len(description_matches)
                         * weight * BASE_SCORE_PER_MATCH)
    base_score = title_score + description_score
    total_score = base_score * article.source_priority

    return {
        'total_score': total_score,
        'title_matches': title_matches,
        'description_matches': description_matches,
        'title_score': title_score,
        'description_score': description_score,
        'weight': weight,
        'source_priority': article.source_priority
    }


def calculate_score(
    article: Article,
    keywords: List[str],
    weight: float
) -> float:
    """
    Berechnet den Relevanz-Score fuer einen Artikel.

    Args:
        article: Artikel mit source_priority.
        keywords: Relevante Keywords fuer dieses Interesse.
        weight: Gewichtungsfaktor aus der Config.

    Returns:
        Score-Wert, hoeher = relevanter.
    """
    if not keywords:
        return 0.0

    breakdown = _compute_score_breakdown(article, keywords, weight)

    logger.debug(
        f"Score fuer '{article.title[:40]}...': "
        f"Titel={len(breakdown['title_matches'])} * "
        f"{TITLE_MULTIPLIER} "
        f"* {weight} = {breakdown['title_score']:.2f}, "
        f"Desc={len(breakdown['description_matches'])} "
        f"* {weight} = {breakdown['description_score']:.2f}, "
        f"Basis={breakdown['title_score'] + breakdown['description_score']:.2f} * "
        f"Prio={article.source_priority} "
        f"= {breakdown['total_score']:.2f}"
    )

    return breakdown['total_score']


def calculate_detailed_score(
    article: Article,
    keywords: List[str],
    weight: float
) -> Dict[str, Any]:
    """Wie calculate_score(), gibt aber die volle Aufschluesselung zurueck."""
    if not keywords:
        return {
            'total_score': 0.0,
            'title_matches': [],
            'description_matches': [],
            'title_score': 0.0,
            'description_score': 0.0,
            'weight': weight,
            'source_priority': article.source_priority
        }

    return _compute_score_breakdown(article, keywords, weight)


def score_all_articles(
    filtered_articles: List[Tuple[Article, List[str], str]],
    interests: List[Dict[str, Any]]
) -> List[Tuple[Article, float, str]]:
    """
    Berechnet Scores fuer alle gefilterten Artikel.

    Score wird ueber alle Interessen kumuliert, d.h. ein Artikel
    der in mehrere Interessen faellt bekommt einen hoeheren Score.

    Args:
        filtered_articles: Tuple (Article, matched_keywords, interest_name)
                          aus dem Filter-Modul.
        interests: Vollstaendige Interest-Konfigurationen.

    Returns:
        Liste von (Article, score, interest_name), absteigend nach Score.
    """
    logger.info(f"Berechne Scores fuer {len(filtered_articles)} Artikel")

    scored_articles: List[Tuple[Article, float, str]] = []

    for article, _, primary_interest_name in filtered_articles:
        # Score ueber alle Interessen kumulieren, nicht nur das primaere
        total_score = _calculate_comprehensive_score(article, interests)

        scored_articles.append((article, total_score, primary_interest_name))

        logger.debug(
            f"Score: {total_score:.2f} fuer '{article.title[:50]}...' "
            f"(Interest: {primary_interest_name})"
        )

    # Relevanteste zuerst
    scored_articles.sort(key=lambda x: x[1], reverse=True)

    # Kurze Zusammenfassung fuers Log
    if scored_articles:
        scores = [score for _, score, _ in scored_articles]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        min_score = min(scores)

        logger.info(
            f"Scoring abgeschlossen: "
            f"Avg={avg_score:.2f}, Max={max_score:.2f}, Min={min_score:.2f}"
        )

    return scored_articles


def _calculate_comprehensive_score(
    article: Article,
    interests: List[Dict[str, Any]]
) -> float:
    """Score ueber alle Interessen aufaddieren.

    Ein Artikel der sowohl "AI" als auch "Security" Keywords
    enthaelt bekommt Punkte aus beiden Bereichen.
    """
    total_score = 0.0

    for interest in interests:
        keywords = interest.get('keywords', [])
        weight = interest.get('weight', 1.0)
        interest_score = calculate_score(article, keywords, weight)
        total_score += interest_score

    return total_score


def filter_by_min_score(
    scored_articles: List[Tuple[Article, float, str]],
    min_score: float
) -> List[Tuple[Article, float, str]]:
    """Artikel unter dem Mindest-Score rausfiltern."""
    # 0 oder negativ = kein Filter
    if min_score <= 0:
        return scored_articles

    filtered = [
        (article, score, interest)
        for article, score, interest in scored_articles
        if score >= min_score
    ]

    logger.info(
        f"Min-Score-Filter: {len(filtered)} von {len(scored_articles)} "
        f"Artikeln haben Score >= {min_score}"
    )

    return filtered


def get_score_distribution(
    scored_articles: List[Tuple[Article, float, str]]
) -> Dict[str, int]:
    """Score-Verteilung in Bereiche aufteilen (fuer Statistik)."""
    distribution = {
        '0-2': 0,
        '2-4': 0,
        '4-6': 0,
        '6-8': 0,
        '8+': 0
    }

    for _, score, _ in scored_articles:
        if score < DISTRIBUTION_BOUNDARIES[0]:
            distribution['0-2'] += 1
        elif score < DISTRIBUTION_BOUNDARIES[1]:
            distribution['2-4'] += 1
        elif score < DISTRIBUTION_BOUNDARIES[2]:
            distribution['4-6'] += 1
        elif score < DISTRIBUTION_BOUNDARIES[3]:
            distribution['6-8'] += 1
        else:
            distribution['8+'] += 1

    return distribution


def get_top_articles(
    scored_articles: List[Tuple[Article, float, str]],
    n: int = 10
) -> List[Tuple[Article, float, str]]:
    """Top n Artikel nach Score (Liste muss vorsortiert sein)."""
    return scored_articles[:n]
