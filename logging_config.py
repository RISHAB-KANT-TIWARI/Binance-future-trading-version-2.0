import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

LOG_DIR = Path(__file__).resolve().parent
LOG_FILE = LOG_DIR / "trading_bot.log"

def setup_logger(name: str = "trading_bot", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    return logger

def log_api_request(logger: logging.Logger, method: str, url: str, params: Optional[dict] = None, data: Optional[Any] = None) -> None:
    # Do NOT log API keys or signatures
    safe_params = {k: ("<redacted>" if "key" in k.lower() or "signature" in k.lower() else v) for k, v in (params or {}).items()}
    logger.info("API Request: %s %s params=%s data=%s", method, url, safe_params, data)

def log_api_response(logger: logging.Logger, status_code: int, body: Any) -> None:
    logger.info("API Response: %s body=%s", status_code, body)