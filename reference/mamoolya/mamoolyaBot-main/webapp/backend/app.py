from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import time
import os
import sqlite3
from datetime import datetime
import random
import hashlib
import hmac
import json
from urllib.parse import parse_qs, unquote

# Пытаемся импортировать функцию для определения знака зодиака
try:
    from zodiac_utils import get_zodiac_sign_by_date
except ImportError:
    # Если не удалось импортировать, создаем заглушку
    def get_zodiac_sign_by_date(day, month):
        return None


# Загружаем .env файл из корня проекта
try:
    from dotenv import load_dotenv

    dotenv_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    load_dotenv(dotenv_path)
except ImportError:
    print("python-dotenv не установлен, используем системные переменные окружения")

app = Flask(__name__)

# Path to static frontend files (SvelteKit build output)
STATIC_PATH = os.environ.get(
    "STATIC_WEB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "frontend", "build"),
)

# Настройка CORS - разрешаем все для разработки
CORS(
    app,
    origins=["*"],  # Разрешаем все домены для разработки
    allow_headers=["*"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    supports_credentials=True,
)

# Режим разработки - отключаем валидацию Telegram
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "true").lower() == "true"

# Секретный ключ бота (получите из переменных окружения)
BOT_TOKEN = os.getenv("TOKEN", "YOUR_BOT_TOKEN_HERE")
BOT_SECRET = hashlib.sha256(BOT_TOKEN.encode()).digest()

CHAT_ID_ENV = os.getenv("CHAT_ID")
try:
    DEFAULT_CHAT_ID = int(CHAT_ID_ENV) if CHAT_ID_ENV else None
except ValueError:
    DEFAULT_CHAT_ID = None

# Путь к базе данных
DB_PATH = os.getenv(
    "DB_PATH", "chat.db"
)

# Создаём таблицы для анонимок и друзей/козлов, если не существуют
with sqlite3.connect(DB_PATH) as conn:
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS anon_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            published BOOLEAN DEFAULT 0,
            published_at DATETIME,
            chat_id INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS friend_foe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_user_id TEXT,
            target_user_id TEXT,
            relation TEXT CHECK(relation IN ('friend','neutral','foe')),
            timestamp TEXT,
            chat_id INTEGER
        )
    """)
    # Создаем таблицу для хранения знака зодиака пользователя
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_zodiac (
            user_id TEXT PRIMARY KEY,
            zodiac_sign TEXT NOT NULL
        )
    """)
    try:
        c.execute("ALTER TABLE friend_foe ADD COLUMN chat_id INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    if DEFAULT_CHAT_ID is not None:
        try:
            c.execute(
                "UPDATE friend_foe SET chat_id = ? WHERE chat_id IS NULL",
                (DEFAULT_CHAT_ID,),
            )
            conn.commit()
        except sqlite3.Error:
            pass

last_anon_time = {}
ANON_COOLDOWN = 120  # 2 минуты


def validate_telegram_data(init_data):
    """Валидация данных от Telegram WebApp"""
    try:
        print(f"[VALIDATE] Начинаем валидацию данных: {init_data[:200]}...")

        if not init_data:
            print(f"[VALIDATE] Данные отсутствуют")
            return None

        # Парсим данные
        try:
            parsed_data = parse_qs(init_data)
            print(f"[VALIDATE] Распарсенные данные: {list(parsed_data.keys())}")
        except Exception as parse_error:
            print(f"[VALIDATE] Ошибка парсинга данных: {parse_error}")
            return None

        # Извлекаем hash и остальные данные
        received_hash = parsed_data.get("hash", [None])[0]
        print(f"[VALIDATE] Получен hash: {received_hash}")

        if not received_hash:
            print(f"[VALIDATE] Hash не найден в данных")
            return None

        # Создаём строку для проверки подписи
        auth_data = []
        for key, value in parsed_data.items():
            if key != "hash":
                auth_data.append(f"{key}={value[0]}")

        auth_data.sort()
        auth_string = "\n".join(auth_data)
        print(f"[VALIDATE] Строка для проверки подписи: {auth_string}")

        # Проверяем подпись
        try:
            expected_hash = hmac.new(
                BOT_SECRET, auth_string.encode(), hashlib.sha256
            ).hexdigest()
            print(f"[VALIDATE] Ожидаемый hash: {expected_hash}")
            print(f"[VALIDATE] Полученный hash: {received_hash}")

            if expected_hash != received_hash:
                print(f"[VALIDATE] Hash не совпадает, валидация не прошла")
                print(f"[VALIDATE] В режиме разработки: {DEVELOPMENT_MODE}")
                # В режиме разработки пропускаем проверку подписи
                if not DEVELOPMENT_MODE:
                    print(
                        f"[VALIDATE] Продакшен режим - отклоняем из-за неверного hash"
                    )
                    return None
                else:
                    print(f"[VALIDATE] Режим разработки - пропускаем проверку подписи")
            else:
                print(f"[VALIDATE] Hash совпадает, валидация прошла")
        except Exception as hash_error:
            print(f"[VALIDATE] Ошибка проверки подписи: {hash_error}")
            if not DEVELOPMENT_MODE:
                return None

        # Парсим user данные
        user_data = parsed_data.get("user", [None])[0]
        print(f"[VALIDATE] Данные пользователя: {user_data}")

        if user_data:
            try:
                user_info = json.loads(unquote(user_data))
                print(f"[VALIDATE] Распарсенная информация о пользователе: {user_info}")

                # Проверяем обязательные поля
                if not user_info.get("id"):
                    print(f"[VALIDATE] ID пользователя отсутствует")
                    return None

                return user_info
            except Exception as user_parse_error:
                print(
                    f"[VALIDATE] Ошибка парсинга данных пользователя: {user_parse_error}"
                )
                return None

        print(f"[VALIDATE] Данные пользователя не найдены")
        return None
    except Exception as e:
        print(f"[VALIDATE] Общая ошибка валидации: {e}")
        import traceback

        traceback.print_exc()
        return None


def get_user_from_request():
    """Получение и валидация пользователя из запроса"""
    print(f"[DEBUG] get_user_from_request: Режим разработки: {DEVELOPMENT_MODE}")

    if DEVELOPMENT_MODE:
        print(f"[DEBUG] Режим разработки включен")

        # Проверяем данные в URL параметрах
        tg_web_app_data = request.args.get("tgWebAppData")
        if tg_web_app_data:
            print(
                f"[DEBUG] Найдены данные в URL параметре tgWebAppData: {tg_web_app_data[:100]}..."
            )
            user = validate_telegram_data(tg_web_app_data)
            if user:
                print(
                    f"[DEBUG] Валидация прошла успешно, возвращаем пользователя: {user}"
                )
                return user
            else:
                print(f"[DEBUG] Валидация не прошла для данных из URL параметра")

        print(f"[DEBUG] Данные в URL параметрах не найдены или валидация не прошла")
        print(f"[DEBUG] tg_web_app_data: {tg_web_app_data}")

        # Проверяем, есть ли хоть какие-то данные Telegram
        if tg_web_app_data:
            print(f"[DEBUG] Данные Telegram найдены, но валидация не прошла")
            print(
                f"[DEBUG] В режиме разработки пытаемся извлечь данные пользователя без валидации"
            )

            # Пытаемся извлечь данные пользователя без проверки подписи
            try:
                parsed_data = parse_qs(tg_web_app_data)
                user_data = parsed_data.get("user", [None])[0]
                if user_data:
                    user_info = json.loads(unquote(user_data))
                    print(
                        f"[DEBUG] Извлечены данные пользователя без валидации: {user_info}"
                    )
                    return user_info
            except Exception as extract_error:
                print(f"[DEBUG] Ошибка извлечения данных пользователя: {extract_error}")

        # В любом случае возвращаем тестового пользователя в режиме разработки
        print(f"[DEBUG] Возвращаем тестового пользователя как fallback")
        return {"id": 1, "first_name": "Test User", "username": "testuser"}

    # В продакшене строгая валидация
    print(f"[DEBUG] Продакшен режим - строгая валидация")

    # Проверяем URL параметры
    tg_web_app_data = request.args.get("tgWebAppData")
    if tg_web_app_data:
        print(f"[DEBUG] Найден URL параметр tgWebAppData: {tg_web_app_data[:100]}...")
        user = validate_telegram_data(tg_web_app_data)
        if user:
            print(f"[DEBUG] Валидация URL параметра прошла успешно")
            return user
        else:
            print(f"[DEBUG] Валидация URL параметра не прошла")

    print(f"[DEBUG] Валидация не прошла, возвращаем None")
    return None


@app.before_request
def validate_user():
    """Middleware для валидации пользователя на всех API endpoints"""
    # Пропускаем валидацию для некоторых endpoints
    if request.path.startswith("/api/") and request.path not in ["/api/health"]:
        print(f"[DEBUG] API запрос: {request.method} {request.path}")
        print(f"[DEBUG] Заголовки: {dict(request.headers)}")
        print(f"[DEBUG] URL параметры: {dict(request.args)}")
        print(f"[DEBUG] Режим разработки: {DEVELOPMENT_MODE}")

        try:
            user = get_user_from_request()
            print(f"[DEBUG] Результат get_user_from_request: {user}")

            if not user:
                print(f"[DEBUG] Пользователь не найден, возвращаем 401")
                return (
                    jsonify(
                        {
                            "error": "Неверные данные авторизации",
                            "debug_info": {
                                "development_mode": DEVELOPMENT_MODE,
                                "has_telegram_param": bool(
                                    request.args.get("tgWebAppData")
                                ),
                                "path": request.path,
                            },
                        }
                    ),
                    401,
                )

            # Сохраняем данные пользователя в request для использования в handlers
            request.user = user
            print(
                f"[DEBUG] Пользователь установлен: {user['id']} - {user['first_name']}"
            )

        except Exception as e:
            print(f"[DEBUG] Ошибка в middleware validate_user: {e}")
            import traceback

            traceback.print_exc()
            return (
                jsonify(
                    {
                        "error": "Ошибка сервера при валидации",
                        "debug_info": {
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "development_mode": DEVELOPMENT_MODE,
                        },
                    }
                ),
                500,
            )


@app.route("/api/anon", methods=["POST"])
def anon():
    data = request.get_json()
    user = request.user

    if not data or not data.get("message"):
        return jsonify({"error": "Пустое сообщение"}), 400

    # Проверка на спам
    user_id = int(user["id"])  # Преобразуем в int, как в боте
    if str(user_id) in last_anon_time:
        time_diff = time.time() - last_anon_time[str(user_id)]
        if time_diff < ANON_COOLDOWN:
            remaining = int(ANON_COOLDOWN - time_diff)
            return jsonify({"error": f"Подождите {remaining} секунд"}), 429

    # Сохранение сообщения
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        current_chat_id = int(os.getenv("CHAT_ID", "0"))
        c.execute(
            """
            INSERT INTO anon_messages (created_at, user_id, username, first_name, message, published, published_at, chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datetime.now().isoformat(),
                user_id,  # Сохраняем как int
                user.get("username", ""),
                user.get("first_name", ""),
                data["message"],
                0,  # published - по умолчанию не опубликовано
                None,  # published_at - по умолчанию не установлено
                current_chat_id,
            ),
        )
        anon_id = c.lastrowid
        conn.commit()

    last_anon_time[str(user_id)] = time.time()  # Сохраняем как строку для совместимости

    # НЕМЕДЛЕННАЯ ПУБЛИКАЦИЯ анонимного сообщения
    try:
        import asyncio
        import threading
        from telegram.ext import Application

        def publish_now():
            try:
                # Создаем event loop для потока
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def async_publish():
                    try:
                        # Создаем приложение Telegram
                        app = Application.builder().token(os.getenv("TOKEN")).build()
                        await app.initialize()

                        # Публикуем сообщение немедленно
                        text = f"{data['message']}\n\n_Анонимка №{anon_id}_"
                        chat_id = int(os.getenv("CHAT_ID", 0))
                        await app.bot.send_message(
                            chat_id=chat_id, text=text, parse_mode="Markdown"
                        )

                        # Обновляем статус в базе данных
                        with sqlite3.connect(DB_PATH) as conn:
                            c = conn.cursor()
                            now = datetime.now().isoformat(sep=" ", timespec="seconds")
                            c.execute(
                                "UPDATE anon_messages SET published=1, published_at=?, chat_id=? WHERE id=?",
                                (now, chat_id, anon_id),
                            )
                            conn.commit()

                        await app.shutdown()
                    except Exception as e:
                        print(f"Ошибка при немедленной публикации: {e}")

                loop.run_until_complete(async_publish())
                loop.close()
            except Exception as e:
                print(f"Ошибка в потоке публикации: {e}")

        # Запускаем публикацию в отдельном потоке
        thread = threading.Thread(target=publish_now)
        thread.start()

        return jsonify(
            {
                "success": True,
                "message": "Анонимка отправлена и будет немедленно опубликована!",
            }
        )
    except Exception as e:
        print(f"Ошибка при запуске немедленной публикации: {e}")
        # Если немедленная публикация не удалась, сообщение останется в базе для позже публикации
        return jsonify({"success": True, "message": "Анонимка отправлена!"})


@app.route("/api/stats")
def stats():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM anon_messages")
        anon_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM friend_foe")
        votes_count = c.fetchone()[0]

        return jsonify({"anon_messages": anon_count, "friend_foe_votes": votes_count})


@app.route("/api/user_stats")
def user_stats():
    user = request.user
    user_id = str(user["id"])

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Количество анонимок от пользователя
        c.execute("SELECT COUNT(*) FROM anon_messages WHERE user_id = ?", (user_id,))
        user_anon_count = c.fetchone()[0]

        # Количество голосов от пользователя
        if DEFAULT_CHAT_ID is not None:
            c.execute(
                "SELECT COUNT(*) FROM friend_foe WHERE voter_user_id = ? AND chat_id = ?",
                (user_id, DEFAULT_CHAT_ID),
            )
        else:
            c.execute(
                "SELECT COUNT(*) FROM friend_foe WHERE voter_user_id = ?", (user_id,)
            )
        user_votes_count = c.fetchone()[0]

        # Количество голосов за пользователя
        if DEFAULT_CHAT_ID is not None:
            c.execute(
                "SELECT COUNT(*) FROM friend_foe WHERE target_user_id = ? AND chat_id = ?",
                (user_id, DEFAULT_CHAT_ID),
            )
        else:
            c.execute(
                "SELECT COUNT(*) FROM friend_foe WHERE target_user_id = ?", (user_id,)
            )
        votes_about_user = c.fetchone()[0]

        # Разбивка по типам голосов за пользователя
        breakdown_query = """
            SELECT relation, COUNT(*) FROM friend_foe 
            WHERE target_user_id = ?
        """
        breakdown_params = [user_id]
        if DEFAULT_CHAT_ID is not None:
            breakdown_query += " AND chat_id = ?"
            breakdown_params.append(DEFAULT_CHAT_ID)
        breakdown_query += " GROUP BY relation"
        c.execute(breakdown_query, tuple(breakdown_params))
        votes_breakdown = dict(c.fetchall())

        return jsonify(
            {
                "user_anon_count": user_anon_count,
                "user_votes_count": user_votes_count,
                "votes_about_user": votes_about_user,
                "votes_breakdown": votes_breakdown,
            }
        )


@app.route("/api/friends/anketa")
def friend_foe_anketa():
    user = request.user
    voter_user_id = str(user["id"])  # Ensure it's a string for comparison

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Получаем список всех пользователей
        c.execute("SELECT DISTINCT user_id, username, first_name FROM anon_messages")
        all_users = c.fetchall()

        # Получаем уже проголосованных пользователей
        voted_query = "SELECT target_user_id FROM friend_foe WHERE voter_user_id = ?"
        voted_params = [voter_user_id]
        if DEFAULT_CHAT_ID is not None:
            voted_query += " AND chat_id = ?"
            voted_params.append(DEFAULT_CHAT_ID)
        c.execute(voted_query, tuple(voted_params))
        voted_users = {
            str(row[0]) for row in c.fetchall()
        }  # Ensure strings for comparison

        # Фильтруем пользователей для голосования
        users_to_vote = []
        for user_id, username, first_name in all_users:
            user_id_str = str(user_id)  # Convert to string for comparison
            if user_id_str != voter_user_id and user_id_str not in voted_users:
                users_to_vote.append(
                    {
                        "user_id": user_id_str,  # Use string version
                        "username": username,
                        "first_name": first_name,
                    }
                )

        # Случайный пользователь для голосования
        if users_to_vote:
            random_user = random.choice(users_to_vote)
            return jsonify({"user": random_user, "remaining_count": len(users_to_vote)})
        else:
            return jsonify({"message": "Нет пользователей для голосования"})


@app.route("/api/friends/vote", methods=["POST"])
def friend_foe_vote():
    data = request.get_json()
    user = request.user
    voter_user_id = str(user["id"])

    required_fields = ["target_user_id", "relation"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Отсутствуют обязательные поля"}), 400

    if data["relation"] not in ["friend", "neutral", "foe"]:
        return jsonify({"error": "Неверный тип отношения"}), 400

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Проверяем, не голосовал ли уже этот пользователь за этого человека
        duplicate_query = """
            SELECT id FROM friend_foe 
            WHERE voter_user_id = ? AND target_user_id = ?
        """
        duplicate_params = [voter_user_id, data["target_user_id"]]
        if DEFAULT_CHAT_ID is not None:
            duplicate_query += " AND chat_id = ?"
            duplicate_params.append(DEFAULT_CHAT_ID)
        c.execute(duplicate_query, tuple(duplicate_params))

        if c.fetchone():
            return jsonify({"error": "Вы уже голосовали за этого пользователя"}), 400

        # Сохраняем голос
        c.execute(
            """
            INSERT INTO friend_foe (voter_user_id, target_user_id, relation, timestamp, chat_id)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                voter_user_id,
                data["target_user_id"],
                data["relation"],
                datetime.now().isoformat(),
                DEFAULT_CHAT_ID,
            ),
        )
        conn.commit()

        return jsonify({"success": True, "message": "Голос сохранен!"})


@app.route("/api/friends/my_lists")
def friend_foe_my_lists():
    user = request.user
    user_id = str(user["id"])

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Получаем списки друзей и козлов
        base_query = """
            SELECT f.target_user_id, f.relation, a.username, a.first_name
            FROM friend_foe f
            LEFT JOIN anon_messages a ON f.target_user_id = a.user_id
            WHERE f.voter_user_id = ?
        """
        params = [user_id]
        if DEFAULT_CHAT_ID is not None:
            base_query += " AND f.chat_id = ?"
            params.append(DEFAULT_CHAT_ID)
        base_query += " GROUP BY f.target_user_id, f.relation"
        c.execute(base_query, tuple(params))

        results = c.fetchall()

        friends = []
        foes = []
        neutral = []

        for target_user_id, relation, username, first_name in results:
            user_info = {
                "user_id": target_user_id,
                "username": username,
                "first_name": first_name,
            }

            if relation == "friend":
                friends.append(user_info)
            elif relation == "foe":
                foes.append(user_info)
            else:
                neutral.append(user_info)

        return jsonify({"friends": friends, "foes": foes, "neutral": neutral})


@app.route("/api/friends/who_added_me")
def friend_foe_who_added_me():
    user = request.user
    user_id = str(user["id"])

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Получаем всех пользователей
        voters_query = """
            SELECT f.voter_user_id, f.relation, a.username, a.first_name
            FROM friend_foe f
            LEFT JOIN anon_messages a ON f.voter_user_id = a.user_id
            WHERE f.target_user_id = ?
        """
        voters_params = [user_id]
        if DEFAULT_CHAT_ID is not None:
            voters_query += " AND f.chat_id = ?"
            voters_params.append(DEFAULT_CHAT_ID)
        voters_query += " GROUP BY f.voter_user_id, f.relation"
        c.execute(voters_query, tuple(voters_params))

        results = c.fetchall()

        friends = []
        foes = []
        neutral = []

        for voter_user_id, relation, username, first_name in results:
            user_info = {
                "user_id": voter_user_id,
                "username": username,
                "first_name": first_name,
            }

            if relation == "friend":
                friends.append(user_info)
            elif relation == "foe":
                foes.append(user_info)
            else:
                neutral.append(user_info)

        return jsonify({"friends": friends, "foes": foes, "neutral": neutral})


@app.route("/api/user")
def get_user():
    """Получение данных текущего пользователя"""
    user = request.user
    user_id = str(user["id"])

    # Получаем знак зодиака пользователя
    zodiac_sign = None
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT zodiac_sign FROM user_zodiac WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            zodiac_sign = row[0]

    # Формируем URL аватара пользователя
    avatar_url = f"https://krksksoc-maman.up.railway.app/userpics/{user['id']}.jpg"

    # Формируем ответ
    user_data = {
        "id": user["id"],
        "first_name": user.get("first_name", ""),
        "username": user.get("username", ""),
        "avatar_url": avatar_url,
        "zodiac_sign": zodiac_sign,
    }

    # Добавляем дату рождения, если она доступна
    if "birthdate" in user:
        birthdate = user["birthdate"]
        user_data["birthdate"] = {
            "day": birthdate.day,
            "month": birthdate.month,
            "year": birthdate.year if hasattr(birthdate, "year") else None,
        }

        # Если знак зодиака не установлен, пытаемся определить его по дате рождения
        if not zodiac_sign:
            zodiac_sign_from_birthdate = get_zodiac_sign_by_date(
                birthdate.day, birthdate.month
            )
            if zodiac_sign_from_birthdate:
                user_data["zodiac_sign"] = zodiac_sign_from_birthdate
                # Сохраняем определенный знак в базе данных
                try:
                    with sqlite3.connect(DB_PATH) as conn:
                        c = conn.cursor()
                        c.execute(
                            """
                            INSERT OR REPLACE INTO user_zodiac (user_id, zodiac_sign)
                            VALUES (?, ?)
                        """,
                            (user_id, zodiac_sign_from_birthdate),
                        )
                        conn.commit()
                except Exception as e:
                    print(f"Ошибка при сохранении знака зодиака в базе данных: {e}")

    return jsonify(user_data)


@app.route("/api/debug")
def debug_info():
    """Отладочная информация (только в режиме разработки)"""
    if not DEVELOPMENT_MODE:
        return jsonify({"error": "Доступно только в режиме разработки"}), 403

    # Пытаемся получить пользователя
    user = get_user_from_request()

    return jsonify(
        {
            "development_mode": DEVELOPMENT_MODE,
            "request_path": request.path,
            "request_method": request.method,
            "headers": dict(request.headers),
            "args": dict(request.args),
            "form": dict(request.form),
            "url": request.url,
            "user_agent": request.headers.get("User-Agent"),
            "telegram_init_data": request.headers.get("X-Telegram-Init-Data"),
            "tg_webapp_data": request.args.get("tgWebAppData"),
            "parsed_user": user,
            "validation_result": (
                "success"
                if user and user.get("id") != 1631188582
                else "fallback_to_test_user"
            ),
        }
    )


@app.route("/api/test_user_simple")
def test_user_simple():
    """Простой endpoint для получения данных пользователя без валидации middleware"""
    if not DEVELOPMENT_MODE:
        return jsonify({"error": "Доступно только в режиме разработки"}), 403

    user = get_user_from_request()
    return jsonify(
        {
            "user": user,
            "source": (
                "headers"
                if request.headers.get("X-Telegram-Init-Data")
                else (
                    "url_params"
                    if request.args.get("tgWebAppData")
                    else "test_fallback"
                )
            ),
        }
    )


@app.route("/api/health")
def health_check():
    """Endpoint для проверки состояния приложения"""
    try:
        # Получаем информацию о состоянии приложения
        user = None
        validation_error = None

        try:
            user = get_user_from_request()
        except Exception as e:
            validation_error = str(e)

        return jsonify(
            {
                "status": "ok",
                "development_mode": DEVELOPMENT_MODE,
                "bot_token_configured": bool(
                    BOT_TOKEN and BOT_TOKEN != "YOUR_BOT_TOKEN_HERE"
                ),
                "db_path": DB_PATH,
                "has_telegram_param": bool(request.args.get("tgWebAppData")),
                "user_validated": bool(user),
                "validation_error": validation_error,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            500,
        )


@app.route("/api/quotes")
def get_quotes():
    """Endpoint для получения случайной цитаты"""
    print("[DEBUG] Обработка запроса /api/quotes")
    try:
        print(f"[DEBUG] Путь к базе данных: {DB_PATH}")
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()

            # Проверяем, существует ли таблица quotes
            c.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='quotes'"
            )
            table_exists = c.fetchone()
            print(f"[DEBUG] Таблица quotes существует: {bool(table_exists)}")

            if not table_exists:
                # Выводим список всех таблиц
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = c.fetchall()
                print(f"[DEBUG] Список таблиц: {tables}")
                raise Exception("Таблица quotes не найдена в базе данных")

            # Получаем случайную цитату из базы данных
            c.execute("""
                SELECT id, username, message, timestamp, message_id, chat_id 
                FROM quotes 
                ORDER BY RANDOM() 
                LIMIT 10
            """)
            rows = c.fetchall()
            print(f"[DEBUG] Найдено цитат: {len(rows)}")

            # Форматируем результаты
            quotes = []
            for row in rows:
                quote_id, username, message, timestamp, message_id, chat_id = row

                # Создаем ссылку на оригинальное сообщение
                # Формат ссылки: https://t.me/c/{chat_id_without_minus}/{message_id}
                chat_id_for_link = (
                    str(chat_id).replace("-100", "")
                    if str(chat_id).startswith("-100")
                    else str(chat_id)
                )
                message_link = f"https://t.me/c/{chat_id_for_link}/{message_id}"

                quotes.append(
                    {
                        "id": quote_id,
                        "username": username,
                        "message": message,
                        "timestamp": timestamp,
                        "message_link": message_link,
                    }
                )

            print(f"[DEBUG] Отправляем {len(quotes)} цитат")
            return jsonify({"quotes": quotes, "count": len(quotes)})
    except Exception as e:
        print(f"[ERROR] Ошибка при получении цитат: {e}")
        return (
            jsonify({"error": "Ошибка при получении цитат", "debug_info": str(e)}),
            500,
        )


@app.route("/api/zodiac", methods=["POST"])
def set_zodiac():
    """Установка знака зодиака пользователя"""
    try:
        data = request.get_json()
        user = request.user
        user_id = str(user["id"])

        if not data or not data.get("zodiac_sign"):
            return jsonify({"error": "Не указан знак зодиака"}), 400

        zodiac_sign = data["zodiac_sign"]

        # Проверяем, что переданный знак зодиака допустим
        valid_signs = [
            "Овен",
            "Телец",
            "Близнецы",
            "Рак",
            "Лев",
            "Дева",
            "Весы",
            "Скорпион",
            "Стрелец",
            "Козерог",
            "Водолей",
            "Рыбы",
        ]

        if zodiac_sign not in valid_signs:
            return jsonify({"error": "Недопустимый знак зодиака"}), 400

        # Сохраняем знак зодиака в базе данных
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                """
                INSERT OR REPLACE INTO user_zodiac (user_id, zodiac_sign)
                VALUES (?, ?)
            """,
                (user_id, zodiac_sign),
            )
            conn.commit()

        return jsonify(
            {"success": True, "message": f"Знак зодиака установлен: {zodiac_sign}"}
        )
    except sqlite3.Error as e:
        print(f"Ошибка базы данных при установке знака зодиака: {e}")
        return jsonify({"error": "Ошибка базы данных"}), 500
    except Exception as e:
        print(f"Ошибка при установке знака зодиака: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Внутренняя ошибка сервера: {str(e)}"}), 500


@app.route("/api/zodiac")
def get_zodiac():
    """Получение знака зодиака пользователя"""
    try:
        user = request.user
        user_id = str(user["id"])

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "SELECT zodiac_sign FROM user_zodiac WHERE user_id = ?", (user_id,)
            )
            row = c.fetchone()

            if row:
                return jsonify({"zodiac_sign": row[0]})
            else:
                return jsonify({"zodiac_sign": None})
    except sqlite3.Error as e:
        print(f"Ошибка базы данных при получении знака зодиака: {e}")
        return jsonify({"error": "Ошибка базы данных"}), 500
    except Exception as e:
        print(f"Ошибка при получении знака зодиака: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Внутренняя ошибка сервера: {str(e)}"}), 500


# Static file serving for SvelteKit frontend
@app.route("/")
def serve_index():
    """Serve the SvelteKit index.html."""
    return send_from_directory(STATIC_PATH, "index.html")


@app.route("/<path:path>")
def serve_static(path: str):
    """Serve static files or fallback to index.html for SPA routing."""
    # Check if the requested file exists
    if os.path.exists(os.path.join(STATIC_PATH, path)):
        return send_from_directory(STATIC_PATH, path)
    # SPA fallback: return index.html for client-side routing
    return send_from_directory(STATIC_PATH, "index.html")


if __name__ == "__main__":
    print(f"🔧 Режим разработки: {'включен' if DEVELOPMENT_MODE else 'выключен'}")
    if DEVELOPMENT_MODE:
        print("⚠️  Валидация Telegram отключена для тестирования")
    app.run(debug=True, port=5001)
