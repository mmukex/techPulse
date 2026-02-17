# -*- coding: utf-8 -*-
"""
Konfigurations-Loader fuer TechPulse.

Laedt die YAML-Konfiguration, setzt Defaults fuer optionale Felder
und validiert alle Pflichtangaben.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ConfigurationError(Exception):
    """Wird bei ungueltiger oder fehlender Konfiguration geworfen."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        self.config_key = config_key
        super().__init__(message)


def load_config(config_path: str) -> Dict[str, Any]:
    """Laedt die YAML-Datei, setzt Defaults und validiert.

    Reihenfolge: laden -> Defaults anwenden -> validieren, damit
    optionale Felder in der YAML-Datei weggelassen werden koennen.

    Raises:
        ConfigurationError: Bei fehlender Datei, ungueltigem YAML
                           oder fehlgeschlagener Validierung.
    """
    path = Path(config_path)

    if not path.exists():
        raise ConfigurationError(
            f"Konfigurationsdatei nicht gefunden: {config_path}"
        )

    if not path.is_file():
        raise ConfigurationError(
            f"Konfigurationspfad ist keine Datei: {config_path}"
        )

    config = _load_yaml_file(path)
    config = _apply_defaults(config)
    validate_config(config)

    return config


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    """Liest und parst eine einzelne YAML-Datei."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

            if config is None:
                raise ConfigurationError(
                    f"Konfigurationsdatei ist leer: {path}"
                )
            return config

    except yaml.YAMLError as e:
        raise ConfigurationError(
            f"YAML-Syntaxfehler in der Konfiguration: {e}"
        )
    except IOError as e:
        raise ConfigurationError(
            f"Konfigurationsdatei nicht lesbar: {e}"
        )


def _apply_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Setzt Standardwerte fuer optionale Konfigurationsabschnitte.

    Nutzt setdefault(), damit vorhandene Werte nicht ueberschrieben
    werden.
    """
    defaults = {
        'logging': {
            'level': 'INFO',
            'directory': 'logs',
            'filename': 'aggregator.log',
            'format': (
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ),
            'console': True
        },
        'output': {
            'directory': 'output',
            'filename_prefix': 'techpulse_report',
            'max_articles': 50,
            'min_score': 0.5
        },
        'fetching': {
            'timeout': 10,
            'max_workers': 5,
            'user_agent': 'TechPulse RSS Aggregator/1.0'
        }
    }

    for section, section_defaults in defaults.items():
        config.setdefault(section, {})
        for key, value in section_defaults.items():
            config[section].setdefault(key, value)

    config.setdefault('feeds', [])
    config.setdefault('interests', [])

    return config


def validate_config(config: Dict[str, Any]) -> bool:
    """Prueft die Konfiguration auf Vollstaendigkeit und Korrektheit."""
    _validate_feeds(config.get('feeds', []))
    _validate_interests(config.get('interests', []))
    _validate_logging(config.get('logging', {}))
    _validate_output(config.get('output', {}))
    return True


def _validate_feeds(feeds: List[Dict[str, Any]]) -> None:
    """Stellt sicher, dass alle Feeds name, url und category haben."""
    if not feeds:
        raise ConfigurationError(
            "Keine Feeds konfiguriert. "
            "Mindestens ein RSS-Feed ist erforderlich.",
            config_key="feeds"
        )

    required_fields = ['name', 'url', 'category']

    for idx, feed in enumerate(feeds):
        for field in required_fields:
            if field not in feed or not feed[field]:
                raise ConfigurationError(
                    f"Feed #{idx + 1}: '{field}' fehlt oder ist leer",
                    config_key=f"feeds[{idx}].{field}"
                )

        # Nur Schema pruefen
        url = feed['url']
        if not url.startswith(('http://', 'https://')):
            raise ConfigurationError(
                f"Feed '{feed['name']}': URL '{url}' muss mit "
                "http:// oder https:// beginnen.",
                config_key=f"feeds[{idx}].url"
            )


def _validate_interests(
    interests: List[Dict[str, Any]]
) -> None:
    """Prueft ob alle Interessen Name, Keywords und gueltiges Gewicht haben."""
    if not interests:
        raise ConfigurationError(
            "Keine Interessen konfiguriert. "
            "Mindestens ein Interesse mit Keywords ist erforderlich.",
            config_key="interests"
        )

    for idx, interest in enumerate(interests):
        if 'name' not in interest or not interest['name']:
            raise ConfigurationError(
                f"Interesse #{idx + 1}: 'name' fehlt oder ist leer",
                config_key=f"interests[{idx}].name"
            )

        keywords = interest.get('keywords', [])
        if not keywords or not isinstance(keywords, list):
            raise ConfigurationError(
                f"Interesse '{interest.get('name', idx + 1)}': "
                "Mindestens ein Keyword erforderlich",
                config_key=f"interests[{idx}].keywords"
            )

        # Gewicht muss positiv sein, sonst wird das Scoring verfaelscht
        weight = interest.get('weight', 1.0)
        if not isinstance(weight, (int, float)) or weight <= 0:
            raise ConfigurationError(
                f"Interesse '{interest['name']}': "
                f"Gewicht '{weight}' ist ungueltig (muss > 0 sein).",
                config_key=f"interests[{idx}].weight"
            )


def _validate_logging(logging_config: Dict[str, Any]) -> None:
    """Validiert das Log-Level gegen die erlaubten Python-Level."""
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    level = logging_config.get('level', 'INFO').upper()
    if level not in valid_levels:
        raise ConfigurationError(
            f"Ungueltiges Log-Level '{level}'. "
            f"Erlaubt: {', '.join(valid_levels)}",
            config_key="logging.level"
        )


def _validate_output(output_config: Dict[str, Any]) -> None:
    """Prueft max_articles und min_score auf gueltige Werte."""
    max_articles = output_config.get('max_articles', 50)
    if not isinstance(max_articles, int) or max_articles < 0:
        raise ConfigurationError(
            f"max_articles={max_articles} ungueltig "
            "(muss nicht-negative Ganzzahl sein).",
            config_key="output.max_articles"
        )

    min_score = output_config.get('min_score', 0.5)
    if not isinstance(min_score, (int, float)) or min_score < 0:
        raise ConfigurationError(
            f"min_score={min_score} ungueltig "
            "(muss nicht-negative Zahl sein).",
            config_key="output.min_score"
        )
