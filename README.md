# TechPulse - RSS Tech-News-Aggregator

RSS-Aggregator der Tech-News aus verschiedenen Feeds sammelt, nach Keywords filtert und als HTML-Report ausgibt.

## Features

- **RSS-Feed Aggregation**: Paralleler Abruf mehrerer RSS/Atom-Feeds
- **Keyword-Filterung**: Case-insensitive Suche in Titel und Beschreibung
- **Intelligentes Scoring**: Relevanz-Bewertung basierend auf Keyword-Matches und konfigurierbaren Gewichten
- **HTML-Reports**: Übersichtliche, responsive Reports mit Farbcodierung
- **Konfigurierbar**: Alle Einstellungen über YAML-Datei anpassbar
- **Logging**: Umfassendes Logging für Debugging und Monitoring

## Installation

### Voraussetzungen

- Python 3.11 oder höher
- pip oder uv als Package-Manager

### Virtuelle Umgebung einrichten (empfohlen)

Eine virtuelle Umgebung isoliert die Projekt-Abhängigkeiten vom System-Python:

```bash
# Virtuelle Umgebung erstellen
python3 -m venv .venv

# Virtuelle Umgebung aktivieren
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Prüfen ob die richtige Python-Version aktiv ist
python --version
```

### Installation der Abhängigkeiten

```bash
# Mit pip (innerhalb der virtuellen Umgebung)
pip install -r requirements.txt

# Oder mit uv
uv pip install -r requirements.txt
```

### Abhängigkeiten

- **feedparser** (>=6.0.10): Universal RSS/Atom Feed Parser
- **pyyaml** (>=6.0): YAML Parser für Konfigurationsdateien
- **jinja2** (>=3.1.2): Template Engine für HTML-Reports

## Verwendung

### Einfache Ausführung

```bash
python main.py
```

### Mit eigener Konfiguration

```bash
python main.py --config path/to/config.yaml
```

### Ausführliche Ausgabe (Debug-Modus)

```bash
python main.py --verbose
```

### Testlauf ohne Report-Speicherung

```bash
python main.py --dry-run
```

### Alle Optionen

```bash
python main.py --help
```

## Konfiguration

Die Konfiguration erfolgt über `config/config.yaml`. Hier können folgende Einstellungen angepasst werden:

### Feeds

```yaml
feeds:
  - name: "Heise Developer"
    url: "https://www.heise.de/developer/rss/news-atom.xml"
    category: "Tech News DE"
```

### Interessen mit Keywords

```yaml
interests:
  - name: "Künstliche Intelligenz"
    keywords:
      - "AI"
      - "Machine Learning"
      - "Deep Learning"
    weight: 2.0  # Höhere Gewichtung für wichtigere Themen
```

### Output-Einstellungen

```yaml
output:
  directory: "output"
  filename_prefix: "techpulse_report"
  max_articles: 50
  min_score: 0.5  # Minimaler Score für Aufnahme in Report
```

### Logging

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  directory: "logs"
  filename: "aggregator.log"
  console: true
```

## Projektstruktur

```
techPulse/
├── src/
│   ├── __init__.py           # Package-Initialisierung
│   ├── logger.py             # Zentrale Logging-Konfiguration
│   ├── config_loader.py      # YAML-Konfiguration laden/validieren
│   ├── feed_parser.py        # RSS-Feed Abruf und Parsing
│   ├── filter.py             # Keyword-basierte Filterung
│   ├── scorer.py             # Scoring-System
│   └── output_generator.py   # HTML-Report Generator
├── templates/
│   └── report_template.html  # Jinja2 HTML-Template
├── config/
│   └── config.yaml           # Konfigurationsdatei
├── output/                   # Generierte Reports
├── logs/                     # Log-Dateien
├── main.py                   # Hauptprogramm
├── requirements.txt          # Dependencies
└── README.md                 # Diese Dokumentation
```

## Scoring-System

Das Scoring bewertet die Relevanz jedes Artikels:

```
Score = (Beschreibungs-Matches × Weight) + (Titel-Matches × 1.5 × Weight)
```

- Titel-Matches zählen 1.5× mehr als Beschreibungs-Matches
- Das `weight` aus der Konfiguration multipliziert den Score
- Höherer Score = höhere Relevanz

### Score-Level im Report

| Score | Level | Farbe |
|-------|-------|-------|
| < 3   | Low   | Gelb  |
| 3-6   | Medium| Blau  |
| >= 6  | High  | Grün  |

## Beispiel-Output

Nach der Ausführung wird ein HTML-Report im `output/`-Verzeichnis erstellt:

```
output/techpulse_report_20240115_143052.html
```

Der Report enthält:
- Statistik-Übersicht (Anzahl Artikel, Durchschnitts-Score, etc.)
- Artikel gruppiert nach Interessengebiet
- Score-Badge mit Farbcodierung
- Direktlinks zu den Originalartikeln

## Logging

Logs werden in `logs/aggregator.log` geschrieben:

```
2024-01-15 14:30:52 - techpulse - INFO - TechPulse gestartet
2024-01-15 14:30:52 - techpulse - INFO - Rufe Feed ab: Heise Developer
2024-01-15 14:30:53 - techpulse - INFO - Feed Heise Developer: 25 Artikel gefunden
...
```

## Tests

Das Projekt enthält Unit-Tests für die Kernmodule (Filter, Scorer, Config-Loader):

```bash
# Alle Tests ausführen
python -m pytest tests/ -v

# Oder mit unittest
python -m unittest discover tests/ -v
```

## Lizenz

Dieses Projekt wurde zu Lernzwecken erstellt.

## Autor

mmukex
