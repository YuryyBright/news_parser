# infrastructure/config/logger.py
import logging.config
import os
from src.config.settings import get_settings

def setup_logging() -> None:
    settings = get_settings()
    
    # Переконуємось, що папка для логів існує
    os.makedirs("logs", exist_ok=True)
    
    is_dev = settings.is_dev
    log_level = settings.logging.level.upper()
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            # Форматтер для кольорової консолі
            "colored_console": {
                "()": "colorlog.ColoredFormatter",
                "format": "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s%(reset)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "log_colors": {
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                }
            },
            # Стандартний форматтер для файлу (без ANSI кодів кольору)
            "standard_file": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}',
            },
        },
        "handlers": {
            # Хендлер для виводу в консоль
            "console": {
                "formatter": "colored_console" if is_dev else settings.logging.format,
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            # Хендлер для запису у файл
            "file": {
                "formatter": "json" if not is_dev else "standard_file",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": "logs/app.log",
                "maxBytes": 10 * 1024 * 1024,  # Максимальний розмір файлу 10 MB
                "backupCount": 5,              # Зберігати 5 старих файлів
                "encoding": "utf-8",
            },
        },
        "loggers": {
            # Кореневий логер
            "": {
                "handlers": ["console", "file"], # Додано file
                "level": log_level,
            },
            "sqlalchemy.engine": {
                "handlers": ["console", "file"], # Додано file
                "level": "WARNING", 
                "propagate": False,
            },
            # "uvicorn.access": {
            #     "handlers": ["console", "file"], # Додано file
            #     "level": "WARNING",
            #     "propagate": False,
            # },
        },
    }

    logging.config.dictConfig(logging_config)