# Hardening: Error Handling & Logging

## Added
- Global PTB error handler: `bot/handlers/errors.py`
- Central logging config in `main.py`

## Behavior
- Unhandled exceptions are logged with traceback.
- User gets safe fallback message (`Произошла ошибка...`) instead of silent failure.

## Scope
- Covers command handlers, callbacks, and conversation handler failures.
