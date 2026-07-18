import logging

from bot.app import run
from bot.config import load_settings
from bot.db import init_db


if __name__ == "__main__":
    import logging.handlers
    log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    file_handler = logging.handlers.RotatingFileHandler(
        "/srv/openclaw-bus/chat_bot/logs/bot.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
    settings = load_settings()
    init_db(settings.sqlite_path)
    run(settings)
