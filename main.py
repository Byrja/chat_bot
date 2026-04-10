from bot.app import run
from bot.config import load_settings
from bot.db import init_db


if __name__ == "__main__":
    settings = load_settings()
    init_db(settings.sqlite_path)
    run(settings)
