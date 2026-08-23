import logging
import os

from dotenv import load_dotenv

load_dotenv()
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False


def setup_logging() -> None:
    """Configure console + rotating file logging for the complete API."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers when uvicorn reloads/imports the application.
    if not root.handlers:
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(formatter)
        root.addHandler(console)

        file_handler = RotatingFileHandler(
            log_dir / "smart_learning_lab.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    else:
        for handler in root.handlers:
            handler.setLevel(level)
            if handler.formatter is None:
                handler.setFormatter(formatter)

    # Keep useful framework logs visible without becoming excessively noisy.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    _CONFIGURED = True



def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
