import logging

from bot.app import run
from bot.config import load_settings
from bot.db import init_db


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    settings = load_settings()
    init_db(settings.sqlite_path)
    run(settings)
