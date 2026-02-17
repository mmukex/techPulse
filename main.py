#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TechPulse - RSS Tech-News-Aggregator

Feeds abrufen, filtern, scoren und als HTML-Report ausgeben.

Verwendung:
    python main.py --config config/config.yaml --verbose
"""

import argparse
import itertools
import sys
import time

from src.logger import setup_logger
from src.config_loader import load_config, ConfigurationError
from src.feed_parser import fetch_all_feeds
from src.filter import filter_articles, get_keyword_statistics
from src.scorer import (
    score_all_articles, filter_by_min_score, get_score_distribution
)
from src.output_generator import generate_html_report, save_report


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TechPulse - RSS Tech-News-Aggregator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
    python main.py
    python main.py --config my_config.yaml --verbose
    python main.py --dry-run
        """
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        default='config/config.yaml',
        help='Pfad zur YAML-Konfigurationsdatei (Standard: config/config.yaml)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Aktiviert ausführliche Ausgabe (DEBUG-Level Logging)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Überschreibt das Output-Verzeichnis aus der Konfiguration'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Führt alle Schritte aus ohne Report zu speichern'
    )

    return parser.parse_args()


def print_banner() -> None:
    banner = """
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   ████████╗███████╗ ██████╗██╗  ██╗██████╗ ██╗   ██╗██╗      ███████╗███████╗   ║
║   ╚══██╔══╝██╔════╝██╔════╝██║  ██║██╔══██╗██║   ██║██║      ██╔════╝██╔════╝   ║
║      ██║   █████╗  ██║     ███████║██████╔╝██║   ██║██║      ███████╗█████╗     ║
║      ██║   ██╔══╝  ██║     ██╔══██║██╔═══╝ ██║   ██║██║      ╚════██║██╔══╝     ║
║      ██║   ███████╗╚██████╗██║  ██║██║     ╚██████╔╝███████╗ ███████║███████╗   ║
║      ╚═╝   ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝      ╚═════╝ ╚══════╝ ╚══════╝╚══════╝   ║
║                                                                   ║
║                 RSS Tech-News-Aggregator v1.0                     ║
╚═══════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_statistics(
    total_feeds: int,
    total_articles: int,
    filtered_count: int,
    scored_count: int,
    duration: float
) -> None:
    print("\n" + "=" * 60)
    print("                    ZUSAMMENFASSUNG")
    print("=" * 60)
    print(f"  Feeds abgerufen:        {total_feeds}")
    print(f"  Artikel gefunden:       {total_articles}")
    print(f"  Nach Filterung:         {filtered_count}")
    print(f"  Im Report:              {scored_count}")
    print(f"  Laufzeit:               {duration:.2f} Sekunden")
    print("=" * 60 + "\n")


def main() -> int:
    """Hauptfunktion: Feeds holen, filtern, scoren, Report bauen.

    Gibt 0 bei Erfolg zurück, 1 bei Fehler.
    """
    start_time = time.time()
    print_banner()
    args = parse_arguments()

    # -- Schritt 1: Konfiguration --
    print(f"[1/5] Lade Konfiguration aus '{args.config}'...")

    try:
        config = load_config(args.config)
        print(f"      -> {len(config['feeds'])} Feeds konfiguriert")
        print(f"      -> {len(config['interests'])} Interessen definiert")
    except ConfigurationError as e:
        print(f"\n[FEHLER] Konfigurationsfehler: {e}")
        return 1
    except FileNotFoundError:
        print(
            f"\n[FEHLER] Konfigurationsdatei nicht gefunden: "
            f"{args.config}"
        )
        return 1

    # CLI-Flags haben Vorrang vor der YAML-Konfiguration
    if args.verbose:
        config['logging']['level'] = 'DEBUG'
    if args.output:
        config['output']['directory'] = args.output

    logger = setup_logger(config)
    logger.info("TechPulse gestartet")

    # -- Schritt 2: Feeds abrufen --
    print("\n[2/5] Rufe RSS-Feeds ab...")

    fetching_config = config.get('fetching', {})
    articles = fetch_all_feeds(
        feed_configs=config['feeds'],
        timeout=fetching_config.get('timeout', 10),
        max_workers=fetching_config.get('max_workers', 5),
        user_agent=fetching_config.get('user_agent', 'TechPulse/1.0')
    )

    total_articles = len(articles)
    print(f"      -> {total_articles} Artikel abgerufen")

    if not articles:
        print("\n[WARNUNG] Keine Artikel gefunden. Feed-URLs prüfen.")
        logger.warning("Keine Artikel aus den Feeds erhalten")

    # -- Schritt 3: Keyword-Filterung --
    print("\n[3/5] Filtere Artikel nach Keywords...")

    filtered_articles = filter_articles(articles, config['interests'])
    filtered_count = len(filtered_articles)
    print(f"      -> {filtered_count} relevante Artikel gefunden")

    if args.verbose and filtered_articles:
        keyword_stats = get_keyword_statistics(filtered_articles)
        print("      -> Top Keywords:")
        for kw, count in itertools.islice(keyword_stats.items(), 5):
            print(f"         - {kw}: {count}x")

    # -- Schritt 4: Scoring --
    print("\n[4/5] Berechne Relevanz-Scores...")

    scored_articles = score_all_articles(
        filtered_articles, config['interests']
    )

    min_score = config['output'].get('min_score', 0)
    if min_score > 0:
        scored_articles = filter_by_min_score(
            scored_articles, min_score
        )
        print(
            f"      -> {len(scored_articles)} Artikel "
            f"mit Score >= {min_score}"
        )

    max_articles = config['output'].get('max_articles', 0)
    if max_articles > 0 and len(scored_articles) > max_articles:
        scored_articles = scored_articles[:max_articles]
        print(f"      -> Begrenzt auf {max_articles} Artikel")

    scored_count = len(scored_articles)

    if args.verbose and scored_articles:
        distribution = get_score_distribution(scored_articles)
        print("      -> Score-Verteilung:")
        for range_str, count in distribution.items():
            if count > 0:
                print(f"         - {range_str}: {count} Artikel")

    # -- Schritt 5: Report generieren --
    print("\n[5/5] Generiere HTML-Report...")

    if args.dry_run:
        html_content = generate_html_report(scored_articles, config)
        print(f"      -> Report generiert ({len(html_content)} Zeichen)")
        print("      -> [DRY-RUN] Report wird nicht gespeichert")
        report_path = None
    else:
        try:
            html_content = generate_html_report(scored_articles, config)
            report_path = save_report(
                html_content=html_content,
                output_dir=config['output']['directory'],
                filename_prefix=config['output'].get(
                    'filename_prefix', 'techpulse_report'
                )
            )
            print(f"      -> Report gespeichert: {report_path}")
        except Exception as e:
            logger.error(f"Report-Generierung fehlgeschlagen: {e}")
            print(f"\n[FEHLER] Report konnte nicht erstellt werden: {e}")
            return 1

    duration = time.time() - start_time

    print_statistics(
        total_feeds=len(config['feeds']),
        total_articles=total_articles,
        filtered_count=filtered_count,
        scored_count=scored_count,
        duration=duration
    )

    # Kurze Vorschau der besten Treffer
    if scored_articles:
        print("Top 3 Artikel:")
        print("-" * 60)
        for i, (article, score, interest) in enumerate(
            scored_articles[:3], 1
        ):
            title = (article.title[:50] + "..."
                     if len(article.title) > 50
                     else article.title)
            print(f"  {i}. [{score:.1f}] {title}")
            print(f"     -> {interest} | {article.feed_name}")
        print("-" * 60)

    if not args.dry_run and scored_articles:
        print("\nReport erfolgreich erstellt!")
        print(f"Öffne im Browser: file://{report_path}")

    logger.info(f"TechPulse beendet ({duration:.2f}s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
