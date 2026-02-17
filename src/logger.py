# -*- coding: utf-8 -*-
"""Logging-Setup fuer TechPulse.

Konfiguriert File- und Konsolen-Handler anhand der YAML-Config.
"""

import logging
from pathlib import Path


def setup_logger(config: dict, name: str = "techpulse") -> logging.Logger:
    """Erstellt und konfiguriert den Anwendungs-Logger.

    Liest die Logging-Einstellungen (Level, Verzeichnis, Format) aus
    dem 'logging'-Abschnitt der Konfiguration und richtet File- und
    optional Console-Handler ein.
    """
    log_config = config.get('logging', {})

    level_name = log_config.get('level', 'INFO').upper()
    # getattr-Fallback auf INFO falls ein ungueltiger Level reinkommt
    log_level = getattr(logging, level_name, logging.INFO)

    log_dir = log_config.get('directory', 'logs')
    log_filename = log_config.get('filename', 'aggregator.log')
    log_format = log_config.get(
        'format',
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    enable_console = log_config.get('console', True)

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / log_filename

    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Bei mehrfachem Aufruf alte Handler rauswerfen, sonst doppelte Eintraege
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(log_format)

    file_handler = _create_file_handler(log_file, formatter, log_level)
    logger.addHandler(file_handler)

    if enable_console:
        console_handler = _create_console_handler(
            formatter, log_level
        )
        logger.addHandler(console_handler)

    logger.debug(f"Logger '{name}' initialisiert (Level: {level_name})")
    logger.debug(f"Log-Datei: {log_file.absolute()}")

    return logger


def _create_file_handler(
    log_file: Path,
    formatter: logging.Formatter,
    level: int
) -> logging.FileHandler:
    """FileHandler fuer die Log-Datei erzeugen."""
    handler = logging.FileHandler(
        filename=str(log_file),
        mode='a',
        encoding='utf-8'
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def _create_console_handler(
    formatter: logging.Formatter,
    level: int
) -> logging.StreamHandler:
    """StreamHandler fuer Konsolenausgabe erzeugen."""
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def get_logger(name: str = "techpulse") -> logging.Logger:
    """Gibt den Logger mit dem angegebenen Namen zurueck."""
    return logging.getLogger(name)
