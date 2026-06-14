# AI_CONTEXT.md — TrainWithBrain (Telegram Web App)

> **Версия документа:** 3.0
> **Последнее обновление:** Июль 2025
> **Назначение:** Рабочий контекст для AI‑агентов. Прочитай этот файл ПЕРВЫМ перед любой задачей.
> **Связанные документы:** [`README.md`](./README.md) (обзор для людей) · [`PROJECT_DETAILS.md`](./PROJECT_DETAILS.md) (глубокий технический разбор) · [`test_result.md`](./test_result.md) (протокол тестирования)

---

## 0. TL;DR для агента (прочитай за 30 секунд)

- **Что это:** Telegram Web App (Mini App) для трекинга силовых тренировок. Открывается внутри Telegram.
- **Стек:** React 19 (CRACO) + FastAPI + MongoDB (Motor). Кастомный UI + shadcn/ui.
- **Текущее состояние:** MVP UI‑скелет. Реализованы: регистрация Telegram‑пользователя в БД, аватар через Bot API, приветствие по времени суток, недельный селектор дней с круговым прогрессом (**прогресс — mock**).
- **Где основной код:** backend → `backend/server.py` (один файл). frontend → `frontend/src/App.js` + `frontend/src/components/DateSelector.js`.
- **Главное правило:** все API‑роуты начинаются с `/api`. URL только из `.env`. ID — только UUID, не ObjectID. Пакеты фронта — только `yarn`.

---

## 1. Суть проекта

**TrainWithBrain (TWB)** — Telegram Web App для отслеживания тренировочного прогресса, ориентированный на пауэрлифтеров и силовых спортсменов. Идея: пользователь открывает приложение прямо в Telegram, видит персональное приветствие, свою тренировочную серию (streak) и недельный календарь с прогрессом выполнения по каждому дню.

### Ключевые особенности
- Интеграция с Telegram WebApp API (`window.Telegram.WebApp`)
- Автоматическая регистрация/обновление пользователя в MongoDB при входе (upsert по `telegram_id`)
- Загрузка аватара пользователя через Telegram Bot API (с fallback на ui-avatars.com)
- Персонализированное приветствие по времени суток
- Недельный селектор дней с круговыми progress‑барами (SVG)
- Mobile‑first адаптивный дизайн (брейкпоинты 374 / 767 / 1023 / 1024px)

---

## 2. Технологический стек (источник истины — `package.json` / `requirements.txt`)

### Frontend
| Технология | Версия | Назначение |
|------------|--------|------------|
| React | 19.0.0 | UI фреймворк |
| CRACO | 7.1.0 | Обёртка над CRA, конфиг webpack, alias `@` → `src` |
| react-scripts (CRA) | 5.0.1 | Сборка |
| Tailwind CSS | 3.4.17 | Утилитарные стили |
| shadcn/ui + Radix UI | latest | Библиотека UI‑компонентов (`src/components/ui/`) |
| react-router-dom | 7.5.1 | Роутинг (сейчас один маршрут `/`) |
| axios | 1.8.4 | HTTP‑запросы к backend |
| lucide-react | 0.507.0 | Иконки |
| recharts | 3.6.0 | Графики (пока не используются) |
| date-fns | 4.1.0 | Работа с датами (пока не используется в коде) |
| sonner | 2.0.3 | Toast‑уведомления |

### Backend
| Технология | Версия | Назначение |
|------------|--------|------------|
| FastAPI | 0.110.1 | Web‑фреймворк |
| Motor | 3.3.1 | Async MongoDB driver |
| Pydantic | 2.x | Валидация данных (используется `ConfigDict(extra="ignore")`) |
| httpx | (зависимость) | Async HTTP‑клиент для вызовов Telegram Bot API |
| python-dotenv | 1.x | Загрузка `.env` |
| uvicorn | 0.25.0 | ASGI‑сервер (запуск через supervisor) |
| emergentintegrations | 0.1.0 | Установлена, но **пока не используется** |

### База данных
- **MongoDB** через Motor (async).
- Имя БД берётся из `DB_NAME` (`.env`), сейчас `test_database`.
- Коллекции: **`users`**, **`status_checks`**.

---

## 3. Структура проекта (актуальная)

```
/app/
├── backend/
│   ├── server.py              # ВЕСЬ backend: модели + все эндпоинты (1 файл)
│   ├── requirements.txt       # Python‑зависимости
│   └── .env                   # MONGO_URL, DB_NAME, CORS_ORIGINS, TELEGRAM_BOT_TOKEN
│
├── frontend/
│   ├── public/
│   │   ├── index.html         # Подключает Telegram, PostHog, Emergent visual-edit скрипты
│   │   ├── TWBlogo.png        # Логотип (рендерится 90x56px)
│   │   ├── gradientcenter.png # Размытый градиент‑свечение в шапке (blur 100px)
│   │   ├── menu.svg           # Иконка меню (40x40px, БЕЗ функционала)
│   │   ├── fire_strike.svg    # Иконка серии тренировок
│   │   ├── arrow-left.svg / arrow-right.svg  # Навигация по неделям
│   │   ├── sunrise.svg        # Утро (05:00–11:59)
│   │   ├── day.svg            # День (12:00–17:59)
│   │   ├── sunset.svg         # Вечер (18:00–22:59)
│   │   └── night.svg          # Ночь (23:00–04:59)
│   │
│   ├── src/
│   │   ├── App.js             # Главный компонент Home: Telegram init, приветствие, streak
│   │   ├── App.css            # Стили шапки/приветствия/streak + адаптив
│   │   ├── index.js           # Точка входа React
│   │   ├── index.css          # Импорт шрифтов, CSS‑переменные, Tailwind, shadcn HSL‑токены
│   │   ├── fonts/             # GGZaglav.woff / .woff2 (кастомный шрифт для крупной даты)
│   │   ├── components/
│   │   │   ├── DateSelector.js   # Недельный селектор дней + ProgressRing (SVG)
│   │   │   ├── DateSelector.css  # Стили карточек дней + адаптив
│   │   │   └── ui/               # 46 компонентов shadcn/ui (.jsx)
│   │   ├── hooks/
│   │   │   └── use-toast.js
│   │   └── lib/
│   │       └── utils.js          # cn() — объединение классов (clsx + tailwind-merge)
│   │
│   ├── package.json
│   ├── craco.config.js        # alias '@', watchOptions, health-check plugin
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── jsconfig.json          # alias '@/*' для IDE
│   └── .env                   # REACT_APP_BACKEND_URL, WDS_SOCKET_PORT, ENABLE_HEALTH_CHECK
│
├── backend_test.py            # Скрипт интеграционного тестирования backend (requests)
├── tests/                     # Пустая директория (__init__)
├── AI_CONTEXT.md              # ← этот файл
├── README.md
├── PROJECT_DETAILS.md
└── test_result.md
```

> ⚠️ В текущем `App.js` в шапке рендерятся ТОЛЬКО логотип и кнопка меню. Элемент аватара в UI пока НЕ выводится, хотя backend‑эндпоинт аватара готов и протестирован. См. раздел 10 (Backlog).

---

## 4. API‑контракт (актуальный)

Базовый префикс: **`/api`** (обязателен для Kubernetes ingress). Все роуты определены в `backend/server.py` через `APIRouter(prefix="/api")`.

| Метод | Endpoint | Назначение | Тело / Параметры | Ответ |
|-------|----------|------------|------------------|-------|
| GET | `/api/` | Health check | — | `{"message": "Hello World"}` |
| POST | `/api/status` | Создать запись статуса | `{ "client_name": str }` | `StatusCheck` |
| GET | `/api/status` | Список статусов (до 1000) | — | `StatusCheck[]` |
| POST | `/api/users` | **Upsert пользователя** по `telegram_id` | `UserCreate` | `User` |
| GET | `/api/users/{telegram_id}` | Получить пользователя | path `telegram_id: int` | `User` (404 если нет) |
| GET | `/api/telegram/avatar/{user_id}` | URL аватара через Bot API | path `user_id: int` | `{ avatar_url, ... }` |

### Модели данных (Pydantic)

```python
# Пользователь — входные данные из Telegram WebApp
class UserCreate(BaseModel):
    telegram_id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

# Пользователь — документ в БД
class User(BaseModel):
    id: str                    # UUID (НЕ ObjectID)
    telegram_id: int
    first_name: str
    last_name: Optional[str]
    username: Optional[str]
    language_code: Optional[str]
    created_at: datetime
    updated_at: datetime

# Демо‑модели из шаблона
class StatusCheck(BaseModel):
    id: str                    # UUID
    client_name: str
    timestamp: datetime
class StatusCheckCreate(BaseModel):
    client_name: str
```

### Поведение `/api/telegram/avatar/{user_id}`
Делает 3 запроса к Telegram Bot API: `getUserProfilePhotos` → `getFile` → формирует прямой URL файла.
Возвращает `{"avatar_url": null, "error": ...}` если: токен не задан / у юзера нет фото / юзер не найден / таймаут (10с). **Никогда не бросает 500** — всегда отдаёт JSON.

### Конвенции сериализации (важно соблюдать в новых эндпоинтах!)
- `datetime` → сохраняется в Mongo как ISO‑строка (`.isoformat()`), при чтении парсится обратно через `datetime.fromisoformat()`.
- Запросы к Mongo всегда исключают `_id`: `find({...}, {"_id": 0})`.
- `id` всегда генерируется как `str(uuid.uuid4())`.

---

## 5. Frontend: ключевые компоненты

### `App.js` → `Home`
1. **Telegram init** (`useEffect`): `tg.ready()`, `tg.expand()`, читает `tg.initDataUnsafe.user`, вызывает `registerUser()` → `POST /api/users`.
2. **Приветствие по времени** (`getGreetingData()`): возвращает текст + иконку в зависимости от часа.
3. **Streak**: статичный текст «Тренировочная серия в течение 0 дней» (значение пока захардкожено).
4. Рендерит `<DateSelector />`.

| Время | Приветствие | Иконка |
|-------|-------------|--------|
| 05:00–11:59 | Доброе утро | `/sunrise.svg` |
| 12:00–17:59 | Добрый день | `/day.svg` |
| 18:00–22:59 | Добрый вечер | `/sunset.svg` |
| 23:00–04:59 | Доброй ночи | `/night.svg` |

### `DateSelector.js`
- Показывает 7 дней текущей недели (Пн→Вс). Навигация по неделям через `weekOffset` (стрелки).
- Каждый день — `DayCard` с `ProgressRing` (SVG, `stroke-dashoffset`).
- Выбранный день подсвечивается градиентом.
- **`MOCK_PROGRESS`** — захардкоженные значения прогресса по дню недели (0–100%). ⚠️ Это mock, реального источника данных нет.
- Под селектором — крупная дата шрифтом `GG Zaglav` (56px).

---

## 6. Дизайн‑система (сверено с CSS)

### Цвета
```css
--bg-main: #1C1C1C;                 /* фон приложения */
--text-primary: #FFFFFF;
--text-secondary: rgba(255,255,255,0.7);
--text-muted: #959595;              /* серый текст (streak) */
Accent / акцент:   #FF6B00          /* оранжевая обводка аватара */
Gradient (выбранный день): linear-gradient(-34deg, #FF8A24, #FFDA24)
Card bg:           #333333          /* карточка дня */
Progress ring bg:  #FFEBD9
Progress ring fill:#FF8A24
shadcn HSL‑токены: заданы в index.css (@layer base :root)
```

### Типографика
| Шрифт | Источник | Использование |
|-------|----------|---------------|
| Plus Jakarta Sans | Google Fonts (400/500/600/700) | Весь основной текст, числа, заголовки |
| GG Zaglav | локальный `src/fonts/GGZaglav.woff2` | Только крупная дата под селектором (56px) |
| SF Pro Display / system | system fallback | Резервный |

### Размеры (mobile ~430px, сверено с CSS)
```
Header padding: 16px 40px (padding-top 40px)
Logo: 90x56px · Menu icon: 40x40px · Avatar (CSS готов): 40x40px, border 2px #FF6B00
Greeting font: 21px · Streak icon: 16x16px · Streak font: 14px
Day card: 64x90px, radius 22px, bg #333
Progress ring wrapper: 44x44px · Week nav button: 35x35px
Selected date title: 56px (шрифт GG Zaglav)
```
Брейкпоинты адаптива: `≤374px`, `≤767px`, `768–1023px`, `≥1024px`.

### Эффекты
1. Свечение в шапке: `gradientcenter.png` с `filter: blur(100px)`, `opacity 0.8`.
2. Прогресс: анимация `stroke-dashoffset 0.3s`.
3. Карточки: hover `scale(1.02)`, active `scale(0.98)`.

---

## 7. Telegram‑интеграция

```javascript
if (window.Telegram?.WebApp) {
  const tg = window.Telegram.WebApp;
  tg.ready();   // сигнал готовности
  tg.expand();  // развернуть на весь экран
  const user = tg.initDataUnsafe?.user; // { id, first_name, last_name, username, language_code, photo_url }
}
```
- **Bot Token** хранится в `backend/.env` → `TELEGRAM_BOT_TOKEN`. Используется только на backend для Bot API.
- **Fallback аватара:** `https://ui-avatars.com/api/?name={first_name}&background=FF6B00&color=fff&size=80&bold=true`.
- ⚠️ Telegram WebApp существует только при открытии внутри Telegram. В обычном браузере `window.Telegram` отсутствует → имя = «Гость», регистрация не вызывается. Это нормально для локальной разработки.

---

## 8. Правила для AI‑агентов (DO / DON'T)

### ❌ НЕ ДЕЛАТЬ
1. ❌ npm — только `yarn` для фронта.
2. ❌ Хардкод URL/портов — всё из `.env`.
3. ❌ MongoDB ObjectID — только UUID (`str(uuid.uuid4())`).
4. ❌ Запуск uvicorn/yarn start вручную — только через supervisor.
5. ❌ Менять значения/URL/порты в `.env`.
6. ❌ `create_file(overwrite=True)` для существующих файлов — использовать `search_replace`.
7. ❌ Реализовывать сторонние интеграции «по памяти» — только через playbook‑эксперта.

### ✅ ДЕЛАТЬ
1. ✅ Все API‑роуты с префиксом `/api`.
2. ✅ В Mongo‑запросах исключать `_id` (`{"_id": 0}`).
3. ✅ Новые datetime сериализовать в ISO‑строку при записи и парсить при чтении.
4. ✅ Новые пакеты добавлять в `requirements.txt` / `package.json`.
5. ✅ После правки `.env` — перезапустить сервис (`sudo supervisorctl restart backend|frontend`).
6. ✅ Frontend → backend всегда через `process.env.REACT_APP_BACKEND_URL` + `/api`.
7. ✅ Перед тестированием — обновлять `test_result.md`, backend тестировать первым.

---

## 9. Команды разработки

```bash
# Зависимости
cd /app/frontend && yarn add <package>
cd /app/backend && pip install <package> && echo "<package>==<version>" >> requirements.txt

# Сервисы
sudo supervisorctl status
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
sudo supervisorctl restart all

# Логи
tail -n 100 /var/log/supervisor/backend.err.log
tail -n 100 /var/log/supervisor/frontend.err.log

# Быстрая проверка backend
curl -s http://localhost:8001/api/
```

---

## 10. Backlog / планируемые функции

### Высокий приоритет
- [ ] Вывести аватар пользователя в шапку (backend‑эндпоинт уже готов; в UI его нет)
- [ ] Регистрация с выбором тренировочного плана
- [ ] API тренировочных планов и упражнений (модели + CRUD)
- [ ] Реальный прогресс по дням вместо `MOCK_PROGRESS`
- [ ] Экран дня: список упражнений (название, подходы, повторы, вес)

### Средний приоритет
- [ ] Отметка выполнения упражнений + расчёт прогресса/streak
- [ ] Реальный подсчёт тренировочной серии (streak) вместо «0»
- [ ] Меню навигации (Sheet/Drawer) — кнопка меню пока без действия
- [ ] Таймер отдыха между подходами, профиль пользователя

### Низкий приоритет
- [ ] Статистика с графиками (recharts уже в зависимостях)
- [ ] Push‑уведомления, экспорт данных, настройки

---

## 11. История изменений

| Дата | Версия | Изменения |
|------|--------|-----------|
| Янв 2025 | 1.0 | Начальная версия (Header, DateSelector) |
| Июль 2025 | 2.0 | Расширена документация |
| Июль 2025 | 3.0 | Полная сверка с кодом: добавлены user/avatar эндпоинты и модели, коллекции, конвенции сериализации, корректные размеры дизайн‑системы, GG Zaglav, CRACO, PostHog; добавлен `PROJECT_DETAILS.md` |

---

## 12. Полезные ссылки
- [Telegram WebApp API](https://core.telegram.org/bots/webapps)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [shadcn/ui](https://ui.shadcn.com/) · [FastAPI](https://fastapi.tiangolo.com/) · [Motor](https://motor.readthedocs.io/)
