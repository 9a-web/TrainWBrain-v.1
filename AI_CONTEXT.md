# AI_CONTEXT.md — TrainWithBrain (Telegram Web App)

## Суть проекта
Telegram Web App для отслеживания тренировочного прогресса, ориентированный на пауэрлифтеров и других силовых спортсменов. Пользователь выбирает тренировочный план при регистрации, получает доступ к "рабочей среде" с расписанием тренировок по дням недели.

## Стек технологий
- **Frontend**: React 19, Tailwind CSS, Shadcn/UI компоненты
- **Backend**: FastAPI (Python), Motor (async MongoDB driver)
- **База данных**: MongoDB
- **Интеграция**: Telegram WebApp API

## Структура проекта
```
/app/
├── backend/
│   ├── server.py          # FastAPI сервер, API endpoints
│   ├── requirements.txt   # Python зависимости
│   └── .env               # Переменные окружения (MONGO_URL, DB_NAME, TELEGRAM_BOT_TOKEN)
├── frontend/
│   ├── public/
│   │   ├── gradientcenter.png  # Декоративный градиент для шапки
│   │   ├── TWBlogo.png         # Логотип TrainWithBrain (90x56px)
│   │   ├── menu.svg            # Иконка меню (40x40px)
│   │   └── index.html          # HTML шаблон
│   ├── src/
│   │   ├── App.js         # Главный компонент приложения
│   │   ├── App.css        # Стили компонентов
│   │   ├── index.css      # Глобальные стили, CSS переменные
│   │   └── components/ui/ # Shadcn/UI компоненты
│   ├── package.json       # Node.js зависимости
│   └── .env               # REACT_APP_BACKEND_URL
└── AI_CONTEXT.md          # Этот файл
```

## Дизайн-система

### Цвета
- **Фон**: `#1C1C1C`
- **Текст основной**: `#FFFFFF`
- **Текст вторичный**: `rgba(255, 255, 255, 0.7)`
- **Акцент (аватарка)**: `#FF6B00` (оранжевый)

### Шрифты
- **Plus Jakarta Sans** — Bold, Medium (основной текст)
- **SF Pro Display** — системный fallback

### Визуальные эффекты
- Градиент в шапке с `filter: blur(100px)` — создаёт мягкое свечение
- Градиент расположен вверху по центру (`top: 0, left: 50%`)

### Отступы
- Header padding: `40px` сверху, `30px` по бокам
- Gap между элементами header-right: `16px`

## Текущие компоненты

### Header (шапка)
- **Слева**: Логотип TWBlogo.png (90x56px)
- **Справа**: 
  - Кнопка меню (menu.svg, 40x40px) — пока без функционала
  - Аватарка пользователя (40x40px, оранжевая рамка 2px)

### Приветствие (main-content)
- Расположение: сразу после header
- Текст: "{Приветствие в зависимости от времени суток}, {имя из Telegram}!"
  - 05:00-11:59 → "Доброе утро" + sunrise.svg
  - 12:00-17:59 → "Добрый день" + day.svg
  - 18:00-22:59 → "Добрый вечер" + sunset.svg
  - 23:00-04:59 → "Доброй ночи" + night.svg
- Иконка: справа от текста (24x24px)
- Шрифт: Plus Jakarta Sans Bold 21px
- Цвет: #FFFFFF
- Fallback имени: "Гость"

### Telegram интеграция
- Аватарка загружается через `window.Telegram.WebApp.initDataUnsafe.user.photo_url`
- Fallback: UI Avatars API с первой буквой имени
- Бот токен: хранится в `backend/.env` как `TELEGRAM_BOT_TOKEN`

## API Endpoints
- `GET /api/` — Health check
- `POST /api/status` — Создание статуса
- `GET /api/status` — Получение всех статусов

## Важные заметки для AI агентов

1. **Не использовать npm** — только yarn для установки пакетов
2. **Все API routes** должны начинаться с `/api`
3. **MongoDB**: исключать `_id` из ответов, использовать projection `{"_id": 0}`
4. **Переменные окружения**: не хардкодить, брать из .env
5. **Hot reload**: при изменении кода сервер перезапускается автоматически, кроме изменений в .env
6. **Shadcn компоненты**: находятся в `/app/frontend/src/components/ui/`

## Планируемые функции (backlog)
- [ ] Регистрация пользователя с выбором тренировочного плана
- [ ] Главный экран с днями недели и упражнениями
- [ ] Карточки упражнений (название, подходы, повторы, вес)
- [ ] Отметка выполнения упражнений
- [ ] Таймер отдыха между подходами
- [ ] Профиль пользователя
- [ ] Меню навигации
- [ ] Статистика прогресса

## Команды разработки
```bash
# Frontend
cd /app/frontend && yarn add [package]

# Backend
cd /app/backend && pip install [package] && pip freeze > requirements.txt

# Перезапуск сервисов (после изменения .env)
sudo supervisorctl restart frontend
sudo supervisorctl restart backend

# Логи
tail -n 100 /var/log/supervisor/backend.err.log
tail -n 100 /var/log/supervisor/frontend.err.log
```
