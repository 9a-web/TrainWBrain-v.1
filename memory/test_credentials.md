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
- Внешний URL приложения (frontend + `/api` + WebSocket `/api/ws`): `https://1db6bd65-9d5b-4875-a5d8-adc82ec9d902.preview.emergentagent.com`
- Backend локально: `http://localhost:8001` (health: `/api/`).
- `frontend/.env` → `REACT_APP_BACKEND_URL=https://1db6bd65-9d5b-4875-a5d8-adc82ec9d902.preview.emergentagent.com` (обновлён под текущий контейнер из env `preview_endpoint`; в склонированном репо был устаревший `avatar-loader-1`, ещё раньше — `c76fc4a8`/`trainbrain-2`). Менять не нужно.
- ⚠️ Google OAuth: в текущем `backend/.env` НЕТ `GOOGLE_CLIENT_ID/SECRET` → прямой Google-вход не работает без ключей и без обновления redirect_uri под новый домен. Email-вход работает.

## Cross-platform (реализовано)
- Website-first + Telegram WebApp (telegram-web-app.js) + PWA (manifest + service-worker + иконки).
- Детект среды: `document.documentElement[data-env]` = `telegram | pwa | web`, `[data-platform]` = `tg.platform`.
- Адаптив: контент центрируется в колонке `max-width: 720px` при `>=768px`; мобильный (<768px) не изменён.

## Seed data (built-in)
- 29 упражнений, 4 шаблона программ: `full-body-beginner`, `upper-lower`, `powerlifting-peaking` (slug), `pl-autumn-3m` («3 мес Подготовка на осень»).

## Google OAuth (direct, own credentials) — added
- Switched from Emergent-managed to DIRECT Google OAuth (own branding on consent screen).
- Config: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in backend/.env (secret NOT stored here).
- Public config endpoint: GET /api/auth/google/config -> {client_id}.
- Flow: frontend redirects to accounts.google.com -> back to <origin>/auth/google?code=... -> POST /api/auth/google/oauth {code, redirect_uri} -> {token, user}.
- Registered redirect URI (Google Console): https://brainjam-1.preview.emergentagent.com/auth/google
- No app-managed password for Google accounts. On deploy, the deployed domain's origin + /auth/google must also be added in Google Console.

## Stats demo account (P7, has data)
- Email: `statsdemo1782072251@example.com`  Password: `password123`
- telegram_id: 950482709876; active plan: pl-autumn-3m (maxes 200/130/230, days [1,3,5]); 9 finished workouts across 3 microcycles.
- Use for /stats and (after linking a coach) /coach/{coach}/clients/950482709876/stats.
