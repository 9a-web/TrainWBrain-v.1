# 🏋️ TrainWithBrain — Telegram Web App

> Приложение для отслеживания тренировочного прогресса пауэрлифтеров и силовых спортсменов

![React](https://img.shields.io/badge/React-19.0.0-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110.1-green)
![MongoDB](https://img.shields.io/badge/MongoDB-Motor-brightgreen)
![Tailwind](https://img.shields.io/badge/Tailwind-3.4.17-38bdf8)

---

## 📖 Описание

**TrainWithBrain** — это Telegram Web App, которое помогает спортсменам планировать и отслеживать свои тренировки. Приложение интегрировано с Telegram и предоставляет удобный интерфейс для:

- 📅 Просмотра расписания тренировок по дням недели
- 📊 Визуализации прогресса выполнения
- ⏱️ Учёта подходов, повторений и весов
- 🔥 Отслеживания тренировочных серий (streak)

---

## 🛠️ Технологии

### Frontend
- **React 19** — UI фреймворк
- **Tailwind CSS 3.4** — стилизация
- **Shadcn/UI** — готовые UI компоненты
- **React Router 7** — маршрутизация
- **Axios** — HTTP запросы

### Backend
- **FastAPI** — Python веб-фреймворк
- **Motor** — асинхронный драйвер MongoDB
- **Pydantic** — валидация данных

### База данных
- **MongoDB** — NoSQL база данных

### Интеграции
- **Telegram WebApp API** — интеграция с Telegram

---

## 📁 Структура проекта

```
/app/
├── backend/                 # FastAPI сервер
│   ├── server.py           # API endpoints
│   ├── requirements.txt    # Python зависимости
│   └── .env                # Переменные окружения
│
├── frontend/               # React приложение
│   ├── public/             # Статические файлы, иконки
│   ├── src/
│   │   ├── App.js          # Главный компонент
│   │   ├── components/     # React компоненты
│   │   │   ├── DateSelector.js  # Выбор дня недели
│   │   │   └── ui/              # Shadcn компоненты
│   │   ├── hooks/          # React hooks
│   │   └── lib/            # Утилиты
│   ├── package.json        # Node зависимости
│   └── .env                # Frontend переменные
│
├── tests/                  # Тесты
├── AI_CONTEXT.md           # Контекст для AI агентов
├── README.md               # Документация (этот файл)
└── test_result.md          # Результаты тестирования
```

---

## 🚀 Быстрый старт

### Предварительные требования
- Node.js 18+
- Python 3.11+
- MongoDB
- Yarn (не npm!)

### Установка

#### 1. Backend
```bash
cd /app/backend
pip install -r requirements.txt
```

#### 2. Frontend
```bash
cd /app/frontend
yarn install
```

### Переменные окружения

#### Backend (.env)
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
CORS_ORIGINS=*
TELEGRAM_BOT_TOKEN=your_bot_token
```

#### Frontend (.env)
```env
REACT_APP_BACKEND_URL=http://localhost:8001
WDS_SOCKET_PORT=443
```

### Запуск (через supervisor)
```bash
sudo supervisorctl start all
```

---

## 📡 API Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/` | Health check |
| POST | `/api/status` | Создать статус |
| GET | `/api/status` | Получить все статусы |

### Пример запроса
```bash
# Health check
curl http://localhost:8001/api/

# Создать статус
curl -X POST http://localhost:8001/api/status \
  -H "Content-Type: application/json" \
  -d '{"client_name": "Test User"}'
```

---

## 🎨 UI Компоненты

### Текущие компоненты

| Компонент | Файл | Описание |
|-----------|------|----------|
| Home | App.js | Главная страница |
| DateSelector | components/DateSelector.js | Выбор дня недели с прогрессом |
| ProgressRing | components/DateSelector.js | Круговой progress bar |

### Shadcn/UI компоненты (46 шт)
Все компоненты находятся в `frontend/src/components/ui/`:
- Button, Card, Dialog, Drawer
- Form, Input, Label
- Sheet, Tabs, Toast
- Progress, Slider, Switch
- И многие другие...

---

## 📱 Telegram интеграция

Приложение использует [Telegram WebApp API](https://core.telegram.org/bots/webapps) для:

1. **Получения данных пользователя:**
   - Имя, фото, username
   - ID пользователя

2. **Управления WebApp:**
   - `tg.ready()` — сигнал готовности
   - `tg.expand()` — развернуть на весь экран

### Использование в коде
```javascript
if (window.Telegram?.WebApp) {
  const tg = window.Telegram.WebApp;
  const user = tg.initDataUnsafe?.user;
  console.log(user.first_name, user.photo_url);
}
```

---

## 🔧 Разработка

### Добавление зависимостей

```bash
# Frontend (ТОЛЬКО yarn!)
cd /app/frontend && yarn add package-name

# Backend
cd /app/backend
pip install package-name
echo "package-name==version" >> requirements.txt
```

### Перезапуск сервисов

```bash
# Перезапуск всех
sudo supervisorctl restart all

# Отдельно frontend
sudo supervisorctl restart frontend

# Отдельно backend
sudo supervisorctl restart backend
```

### Просмотр логов

```bash
# Backend
tail -f /var/log/supervisor/backend.err.log

# Frontend
tail -f /var/log/supervisor/frontend.err.log
```

---

## 📋 Roadmap

### ✅ Выполнено
- [x] Базовая структура проекта
- [x] Header с логотипом и аватаром
- [x] Интеграция с Telegram WebApp API
- [x] Приветствие по времени суток
- [x] DateSelector с progress ring
- [x] Shadcn/UI компоненты

### 🔄 В разработке
- [ ] Регистрация пользователя
- [ ] Выбор тренировочного плана
- [ ] API для упражнений

### 📝 Планируется
- [ ] Карточки упражнений
- [ ] Отметка выполнения
- [ ] Таймер отдыха
- [ ] Профиль пользователя
- [ ] Статистика прогресса

---

## 📚 Документация для AI агентов

Подробный контекст для работы AI агентов находится в файле **[AI_CONTEXT.md](./AI_CONTEXT.md)**:

- Дизайн-система и цвета
- Структура компонентов
- API спецификации
- Правила разработки (DO/DON'T)
- Команды и конфигурация

---

## ⚠️ Важные замечания

1. **Использовать yarn** вместо npm для установки пакетов
2. **Все API роуты** начинаются с `/api`
3. **Не хардкодить URLs** — использовать переменные окружения
4. **MongoDB ObjectID** не использовать — только UUID
5. **Hot reload** работает автоматически, кроме изменений в .env

---

## 📄 Лицензия

Этот проект создан с использованием [Emergent.sh](https://emergent.sh)

---

## 🤝 Контакты

Для вопросов и предложений используйте Telegram бота.
