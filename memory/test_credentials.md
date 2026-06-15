# Test Credentials & Environment Notes — TrainWithBrain

## Auth
- **NEW: Three authentication methods implemented (mandatory auth, no guest mode):**
  1. **Email/Password** — bcrypt hashing, JWT-less session tokens
  2. **Telegram WebApp** — initData HMAC validation with bot token
  3. **Google OAuth** — Emergent Managed Auth (session exchange)
- Every account has a `telegram_id` (real for Telegram users, synthetic 900000000000+ for email/Google)
- Session model: `user_sessions` collection with `session_token`, `telegram_id`, `auth_method`, `expires_at`, `created_at`
- Auth dependency reads `Authorization: Bearer <token>` header first, then `session_token` cookie

### Test Accounts Created (Email Auth)
- **Email**: `authtest+1781538884@example.com`
- **Password**: `password123`
- **telegram_id**: `950454640997` (synthetic)
- **Token**: Session tokens are ephemeral and regenerated on each login

### Test Accounts Created (Telegram Auth)
- **telegram_id**: `123456789` (test account via valid HMAC signature)
- **first_name**: `TestTG`
- **username**: `testtg`

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
