# -*- coding: utf-8 -*-
"""
Feed-Parser fuer TechPulse.

Ruft RSS/Atom-Feeds per feedparser ab und liefert einheitliche
Article-Objekte. Nutzt ThreadPoolExecutor fuer parallelen Abruf.

Autor: mmukex
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from time import mktime

import feedparser

logger = logging.getLogger("techpulse")


@dataclass
class Article:
    """Einzelner Artikel aus einem RSS/Atom-Feed.

    Attributes:
        title: Artikeltitel.
        link: URL zum Originalartikel.
        description: Zusammenfassung oder Teaser.
        published: Veroeffentlichungsdatum.
        feed_name: Anzeigename des Quell-Feeds.
        category: Feed-Kategorie fuer Gruppierung im Report.
        author: Autor, falls im Feed angegeben.
        source_priority: Gewichtung der Quelle im Scoring (Standard: 1.0).
    """

    title: str
    link: str
    description: str = ""
    published: Optional[datetime] = None
    feed_name: str = ""
    category: str = ""
    author: str = ""
    source_priority: float = 1.0

    def __post_init__(self):
        """Whitespace aus Titel und Beschreibung strippen."""
        # Feeds liefern oft fuehrende/folgende Leerzeichen mit
        self.title = self.title.strip() if self.title else ""
        self.description = self.description.strip() if self.description else ""


def fetch_feed(
    url: str,
    name: str,
    category: str,
    priority: float = 1.0,
    timeout: int = 10,
    user_agent: str = "TechPulse RSS Aggregator/1.0"
) -> List[Article]:
    """
    Ruft einen einzelnen RSS/Atom-Feed ab und parst ihn.

    Args:
        url: URL zum Feed.
        name: Anzeigename fuer Logging und Metadaten.
        category: Kategorie zur Gruppierung.
        priority: Quellenpriorität (1.0 = normal, hoeher = wichtiger).
        timeout: HTTP-Timeout in Sekunden.
        user_agent: User-Agent Header.

    Returns:
        Liste der geparsten Artikel, bei Fehlern leer.
    """
    logger.info(f"Rufe Feed ab: {name} ({url})")

    try:
        feed = feedparser.parse(
            url,
            request_headers={'User-Agent': user_agent}
        )

        # bozo-Flag = fehlerhaftes XML, aber manchmal sind trotzdem
        # brauchbare entries drin — nur abbrechen wenn wirklich nichts da ist
        if feed.bozo and not feed.entries:
            error_msg = str(feed.get('bozo_exception', 'Unbekannter Fehler'))
            logger.warning(f"Fehler beim Parsen von {name}: {error_msg}")
            return []

        # feedparser gibt auch bei HTTP-Fehlern ein Objekt zurueck
        status = feed.get('status', 200)
        if status >= 400:
            logger.warning(f"HTTP-Fehler {status} beim Abruf von {name}")
            return []

        # Ungueltige Eintraege (z.B. ohne Titel) werden uebersprungen
        articles = [
            article for entry in feed.entries
            if (article := _parse_feed_entry(
                entry, name, category, priority
            ))
        ]

        logger.info(f"Feed {name}: {len(articles)} Artikel gefunden")
        return articles

    except Exception as e:
        # Netzwerkfehler etc. abfangen, damit andere Feeds weiterlaufen
        logger.error(f"Unerwarteter Fehler beim Abruf von {name}: {e}")
        return []


def _parse_feed_entry(
    entry: Dict[str, Any],
    feed_name: str,
    category: str,
    priority: float = 1.0
) -> Optional[Article]:
    """Konvertiert einen Feed-Eintrag in ein Article.

    Gibt None zurueck wenn Titel oder Link fehlen.
    """
    # Ohne Titel oder Link ist ein Artikel nicht darstellbar
    title = entry.get('title', '').strip()
    if not title:
        logger.debug(f"Eintrag ohne Titel in {feed_name} übersprungen")
        return None

    link = entry.get('link', '').strip()
    if not link:
        logger.debug(f"Eintrag '{title[:30]}...' ohne Link übersprungen")
        return None

    # Optionale Felder rauspicken
    description = _extract_description(entry)
    published = _parse_published_date(entry)
    author = _extract_author(entry)

    return Article(
        title=title,
        link=link,
        description=description,
        published=published,
        feed_name=feed_name,
        category=category,
        author=author,
        source_priority=priority
    )


def _extract_description(entry: Dict[str, Any]) -> str:
    """Beschreibung aus dem Feed-Eintrag holen.

    Prueft mehrere Felder, weil RSS 'description', Atom 'summary'
    und manche Feeds 'content' nutzen.
    """
    description_fields = ['summary', 'description', 'content']

    for field_name in description_fields:
        # 'content' ist ein Sonderfall — kommt als Liste von Dicts
        if field_name == 'content' and field_name in entry:
            content_list = entry.get('content', [])
            if content_list and isinstance(content_list, list):
                return content_list[0].get('value', '').strip()
        else:
            value = entry.get(field_name, '')
            if value:
                return value.strip()

    return ""


def _parse_published_date(entry: Dict[str, Any]) -> Optional[datetime]:
    """Veroeffentlichungsdatum parsen.

    feedparser liefert Daten als time.struct_time — je nach
    Feed-Format in unterschiedlichen Feldern.
    """
    date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']

    for field_name in date_fields:
        time_struct = entry.get(field_name)
        if time_struct:
            try:
                # struct_time -> timestamp -> datetime
                timestamp = mktime(time_struct)
                return datetime.fromtimestamp(timestamp)
            except (ValueError, OverflowError) as e:
                # Manche Feeds haben kaputte Daten (z.B. Jahr 0)
                logger.debug(f"Datum konnte nicht geparst werden: {e}")
                continue

    return None


def _extract_author(entry: Dict[str, Any]) -> str:
    """Autor aus dem Feed-Eintrag holen.

    Kann entweder direkt als String oder verschachtelt
    in 'author_detail' stecken.
    """
    # Erst 'author' direkt versuchen
    author = entry.get('author', '')

    if isinstance(author, dict):
        author = author.get('name', '')

    # Manche Atom-Feeds haben nur author_detail
    if not author:
        author_detail = entry.get('author_detail', {})
        if isinstance(author_detail, dict):
            author = author_detail.get('name', '')

    return author.strip() if isinstance(author, str) else ""


def fetch_all_feeds(
    feed_configs: List[Dict[str, Any]],
    timeout: int = 10,
    max_workers: int = 5,
    user_agent: str = "TechPulse RSS Aggregator/1.0"
) -> List[Article]:
    """
    Ruft mehrere RSS-Feeds parallel ab.

    Args:
        feed_configs: Feed-Konfigurationen mit 'name', 'url',
                     'category' und optional 'priority'.
        timeout: Timeout pro Feed in Sekunden.
        max_workers: Anzahl paralleler Threads.
        user_agent: HTTP User-Agent Header.

    Returns:
        Alle Artikel aus allen Feeds, sortiert nach neustem Datum.
    """
    logger.info(f"Starte parallelen Abruf von {len(feed_configs)} Feeds")

    all_articles: List[Article] = []
    successful_feeds = 0
    failed_feeds = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Future -> Feed-Name Mapping fuer Fehler-Zuordnung
        future_to_feed = {}

        for feed_config in feed_configs:
            feed_priority = feed_config.get('priority', 1.0)

            future = executor.submit(
                fetch_feed,
                url=feed_config['url'],
                name=feed_config['name'],
                category=feed_config['category'],
                priority=feed_priority,
                timeout=timeout,
                user_agent=user_agent
            )
            future_to_feed[future] = feed_config['name']

        # as_completed gibt Futures in Fertigstellungs-Reihenfolge zurueck
        for future in as_completed(future_to_feed):
            feed_name = future_to_feed[future]

            try:
                # +5s Puffer damit der Future-Timeout nicht vor dem HTTP-Timeout greift
                articles = future.result(timeout=timeout + 5)

                if articles:
                    all_articles.extend(articles)
                    successful_feeds += 1
                else:
                    failed_feeds += 1

            except Exception as e:
                logger.error(f"Fehler bei Feed {feed_name}: {e}")
                failed_feeds += 1

    # Neueste zuerst; datetime.min fuer Artikel ohne Datum -> landen am Ende
    all_articles.sort(
        key=lambda a: a.published or datetime.min,
        reverse=True
    )

    logger.info(
        f"Feed-Abruf abgeschlossen: {successful_feeds} erfolgreich, "
        f"{failed_feeds} fehlgeschlagen, {len(all_articles)} Artikel gesamt"
    )

    return all_articles
