from mamoolyaBot.bot import get_filtered_day_messages
from mamoolyaBot.bot import conn
from mamoolyaBot.utils import utctoday

# Test is not self-sufficient. Requires `chat.db` in the project root


def test_select_today_messages():
    conn.set_trace_callback(print)
    today = utctoday()
    msgs = get_filtered_day_messages(today)

    assert len(msgs) > 0
