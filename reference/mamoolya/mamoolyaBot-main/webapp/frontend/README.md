# 🤖 WebApp Мамули - Разделенное приложение

Веб-приложение для Telegram бота с валидацией initDataUnsafe и современным интерфейсом.

## 🔐 Система безопасности

- **Валидация initDataUnsafe**: Все запросы проверяются через подпись Telegram
- **Middleware авторизации**: Автоматическая проверка пользователя на каждом API endpoint
- **Безопасные аватарки**: Использование krksksoc-maman.up.railway.app для изображений профиля

## 📁 Структура проекта

```
mamoolyaApp/
├── backend/                    # Flask API сервер
│   ├── app.py                 # Главный файл API с валидацией
│   ├── start.py               # Скрипт запуска с проверками
│   ├── requirements.txt       # Зависимости Python
│   └── start_local.py        # Старый скрипт запуска
├── src/                       # SvelteKit frontend
│   ├── lib/
│   │   └── api.js            # API утилиты с авторизацией
│   └── routes/
│       ├── +layout.svelte    # Layout с аватаркой и именем
│       ├── +page.svelte      # Главная страница
│       ├── anon/
│       │   └── +page.svelte  # Анонимные сообщения
│       ├── stats/
│       │   └── +page.svelte  # Статистика
│       └── friends/
│           └── +page.svelte  # Друзья и козлы
└── example_webapp/           # Оригинальное приложение
```

## 🚀 Запуск приложения

### 1. Настройка Telegram бота

```bash
# Получите токен от @BotFather
export BOT_TOKEN=your_bot_token_here

# Или создайте файл .env
echo "BOT_TOKEN=your_bot_token_here" > backend/.env
```

### 2. Запуск Backend (Flask API)

```bash
cd backend
pip install -r requirements.txt
python start.py
```

Backend будет доступен на: `http://localhost:5001`

### 3. Запуск Frontend (SvelteKit)

```bash
# Из корневой папки проекта
npm install
npm run dev
```

Frontend будет доступен на: `http://localhost:5173`

### 4. Настройка WebApp в Telegram

1. Откройте @BotFather в Telegram
2. Выберите вашего бота
3. Нажмите 'Bot Settings' → 'Menu Button'
4. Установите URL: `http://localhost:5173`
5. Название кнопки: 'Открыть WebApp'

## 🎨 Новый интерфейс

### Layout
- **Хедер**: Аватарка пользователя и имя из krksksoc-maman.up.railway.app
- **Автоматическая авторизация**: Получение данных пользователя через API
- **Современный дизайн**: Карточки, градиенты, анимации

### Страницы
- **Главная**: Обзор функций с красивыми карточками
- **Анонимки**: Упрощенная форма с валидацией
- **Статистика**: Интерактивные счетчики и рейтинги
- **Друзья**: Карточки для голосования и списки

## 🔧 API Endpoints

### Аутентификация
- `GET /api/user` - получение данных пользователя

### Анонимные сообщения
- `POST /api/anon` - отправка анонимного сообщения

### Статистика
- `GET /api/stats` - общая статистика
- `GET /api/user_stats` - статистика пользователя

### Друзья и козлы
- `GET /api/friends/anketa` - получение анкеты для голосования
- `POST /api/friends/vote` - голосование за пользователя
- `GET /api/friends/my_lists` - мои списки друзей/козлов
- `GET /api/friends/who_added_me` - кто меня добавил

## 🗄️ База данных

Используется SQLite база данных `chat.db` с таблицами:
- `anon_messages` - анонимные сообщения
- `friend_foe` - голосования друзья/козлы

## 🔒 Система валидации

### initDataUnsafe
Все API запросы проверяют подпись Telegram через заголовок `X-Telegram-Init-Data`:

```javascript
// Автоматически добавляется в src/lib/api.js
headers: {
  'X-Telegram-Init-Data': window.Telegram.WebApp.initData
}
```

### Middleware
Flask middleware автоматически валидирует пользователя:

```python
@app.before_request
def validate_user():
    if request.path.startswith('/api/'):
        user = validate_telegram_data(init_data)
        if not user:
            return jsonify({"error": "Неверные данные авторизации"}), 401
        request.user = user
```

## 🖼️ Аватарки

Используется сервис krksksoc-maman.up.railway.app для аватарок:
- URL: `https://krksksoc-maman.up.railway.app/userpics/{user_id}.jpg`
- Fallback: `https://telegram.org/img/t_logo.png`

## 🛠️ Технологии

- **Backend**: Flask, SQLite, Flask-CORS, HMAC валидация
- **Frontend**: SvelteKit, современный CSS, API интеграция
- **Авторизация**: Telegram WebApp initDataUnsafe
- **UI/UX**: Карточки, анимации, градиенты

## 🚀 Продакшен

### Backend
```bash
# Установите переменные окружения
export BOT_TOKEN=your_production_bot_token
export FLASK_ENV=production

# Запустите с gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

### Frontend
```bash
# Соберите проект
npm run build

# Запустите с адаптером
npm run preview
```

### Настройка бота
- Замените `localhost` на ваш домен
- Используйте HTTPS для WebApp URL
- Настройте CORS для продакшена
