# Test Credentials & Environment Notes — TrainWithBrain

## Auth
- **Нет классической аутентификации (логин/пароль).**
- Личность пользователя:
  - В Telegram → реальный `initDataUnsafe.user`.
  - В обычном браузере / PWA → **стойкий web-гость**: `telegram_id` генерируется и хранится в `localStorage` (ключ `twb_web_uid`), имя по умолчанию «Гость» (`twb_web_name`). Данные персистятся на этот браузер.
- Для тестов вне Telegram ничего вводить не нужно — пользователь авто-регистрируется при загрузке (`POST /api/users`).

## URLs
- Внешний URL контейнера (frontend + `/api`): `https://ea220423-ac6a-48fa-9c5a-5a9fc43dfbfb.preview.emergentagent.com`
- Backend локально: `http://localhost:8001` (health: `/api/`).
- `frontend/.env` → `REACT_APP_BACKEND_URL` выровнен с `preview_endpoint` контейнера (исправлен устаревший URL из импортированного с GitHub репозитория).

## Cross-platform (реализовано)
- Website-first + Telegram WebApp (telegram-web-app.js) + PWA (manifest + service-worker + иконки).
- Детект среды: `document.documentElement[data-env]` = `telegram | pwa | web`, `[data-platform]` = `tg.platform`.
- Адаптив: контент центрируется в колонке `max-width: 720px` при `>=768px`; мобильный (<768px) не изменён.

## Seed data (built-in)
- 29 упражнений, 4 шаблона программ: `full-body-beginner`, `upper-lower`, `powerlifting-peaking` (slug), `pl-autumn-3m` («3 мес Подготовка на осень»).
