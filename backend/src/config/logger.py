# infrastructure/config/logger.py
import logging.config
from src.config.settings import get_settings

def setup_logging() -> None:
    settings = get_settings()
    
    # Визначаємо базовий форматтер залежно від середовища
    is_dev = settings.is_dev
    log_level = settings.logging.level.upper()
    
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                # Для production часто зручніше писати логи у JSON (наприклад, для ELK/Datadog)
                "format": '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}',
            },
        },
        "handlers": {
            "default": {
                "formatter": "console" if is_dev else settings.logging.format,
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            # Кореневий логер
            "": {
                "handlers": ["default"],
                "level": log_level,
            },
            # Можна приглушити надто шумні сторонні бібліотеки
            "sqlalchemy.engine": {
                "handlers": ["default"],
                "level": "WARNING", 
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)