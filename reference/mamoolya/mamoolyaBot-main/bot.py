from dotenv import load_dotenv

from mamoolyaBot.bot import (
    mamoolyaMain,
    bottle_game,
    bottle_join_button,
    get_filtered_day_messages,
    auto_publish_anons,
)

__all__ = [
    "mamoolyaMain",
    "bottle_game",
    "bottle_join_button",
    "get_filtered_day_messages",
    "auto_publish_anons",
]


if __name__ == "__main__":
    load_dotenv()  # by default - file with the name '.env', next to this script.
    mamoolyaMain()
