from bot.app import run
from bot.config import load_settings


if __name__ == "__main__":
    settings = load_settings()
    run(settings)
