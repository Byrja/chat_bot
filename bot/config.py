import os
from dataclasses import dataclass


@dataclass
class Settings:
    telegram_bot_token: str
    main_chat_id: int
    admin_chat_id: int
    admin_user_ids: set[int]
    sqlite_path: str
    app_env: str
    main_questionnaires_thread_id: int | None = None
    admin_questionnaires_thread_id: int | None = None


def load_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    main_chat_id = int(os.getenv("MAIN_CHAT_ID", "0") or 0)
    admin_chat_id = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
    admin_raw = os.getenv("ADMIN_USER_IDS", "")
    admins = {int(x.strip()) for x in admin_raw.split(",") if x.strip().isdigit()}
    sqlite_path = os.getenv("SQLITE_PATH", "./data/md4.db")
    app_env = os.getenv("APP_ENV", "dev").strip().lower()
    main_q_thread_raw = (os.getenv("MAIN_QUESTIONNAIRES_THREAD_ID", "") or "").strip()
    admin_q_thread_raw = (os.getenv("ADMIN_QUESTIONNAIRES_THREAD_ID", "") or "").strip()
    main_q_thread = int(main_q_thread_raw) if main_q_thread_raw.isdigit() else None
    admin_q_thread = int(admin_q_thread_raw) if admin_q_thread_raw.isdigit() else None
    return Settings(
        telegram_bot_token=token,
        main_chat_id=main_chat_id,
        admin_chat_id=admin_chat_id,
        admin_user_ids=admins,
        sqlite_path=sqlite_path,
        app_env=app_env,
        main_questionnaires_thread_id=main_q_thread,
        admin_questionnaires_thread_id=admin_q_thread,
    )
