# AI_CONTEXT.md — TrainWithBrain (Telegram Web App)

> **Версия документа:** 2.0  
> **Последнее обновление:** Июль 2025  
> **Назначение:** Контекст для AI агентов при разработке

---

## 🎯 Суть проекта

**TrainWithBrain** — Telegram Web App для отслеживания тренировочного прогресса, ориентированный на пауэрлифтеров и силовых спортсменов. Пользователь выбирает тренировочный план при регистрации и получает доступ к "рабочей среде" с расписанием тренировок по дням недели.

### Ключевые особенности:
- Интеграция с Telegram WebApp API
- Персонализированное приветствие по времени суток
- Визуальный трекинг прогресса с круговыми progress-барами
- Адаптивный дизайн для мобильных устройств

---

## 🛠️ Технологический стек

### Frontend
| Технология | Версия | Назначение |
|------------|--------|------------|
| React | 19.0.0 | UI фреймворк |
| Tailwind CSS | 3.4.17 | Утилитарные стили |
| Shadcn/UI | latest | UI компоненты |
| react-router-dom | 7.5.1 | Роутинг |
| axios | 1.8.4 | HTTP запросы |
| lucide-react | 0.507.0 | Иконки |
| date-fns | 4.1.0 | Работа с датами |
| recharts | 3.6.0 | Графики |

### Backend
| Технология | Версия | Назначение |
|------------|--------|------------|
| FastAPI | 0.110.1 | Web фреймворк |
| Motor | 3.3.1 | Async MongoDB driver |
| Pydantic | 2.6.4+ | Валидация данных |
| python-dotenv | 1.0.1+ | Переменные окружения |
| uvicorn | 0.25.0 | ASGI сервер |

### База данных
- **MongoDB** (через Motor для async операций)
- **Database name:** `test_database` (из .env)

---

## 📁 Структура проекта

```
/app/
├── backend/
│   ├── server.py              # FastAPI сервер, API endpoints
│   ├── requirements.txt       # Python зависимости
│   └── .env                   # Переменные окружения
│       ├── MONGO_URL          # MongoDB connection string
│       ├── DB_NAME            # Имя базы данных
│       ├── CORS_ORIGINS       # CORS настройки
│       └── TELEGRAM_BOT_TOKEN # Токен Telegram бота
│
├── frontend/
│   ├── public/
│   │   ├── TWBlogo.png        # Логотип (90x56px)
│   │   ├── gradientcenter.png # Градиент для header
│   │   ├── menu.svg           # Иконка меню (40x40px)
│   │   ├── fire_strike.svg    # Иконка серии тренировок
│   │   ├── sunrise.svg        # Утро (05:00-11:59)
│   │   ├── day.svg            # День (12:00-17:59)
│   │   ├── sunset.svg         # Вечер (18:00-22:59)
│   │   ├── night.svg          # Ночь (23:00-04:59)
│   │   └── index.html         # HTML шаблон
│   │
│   ├── src/
│   │   ├── App.js             # Главный компонент, Home page
│   │   ├── App.css            # Стили компонентов
│   │   ├── index.js           # Точка входа React
│   │   ├── index.css          # Глобальные стили, CSS переменные
│   │   │
│   │   ├── components/
│   │   │   ├── DateSelector.js    # Компонент выбора дня недели
│   │   │   ├── DateSelector.css   # Стили DateSelector
│   │   │   └── ui/                # 46 Shadcn/UI компонентов
│   │   │       ├── button.jsx
│   │   │       ├── card.jsx
│   │   │       ├── dialog.jsx
│   │   │       ├── drawer.jsx
│   │   │       ├── form.jsx
│   │   │       ├── input.jsx
│   │   │       ├── progress.jsx
│   │   │       ├── sheet.jsx
│   │   │       ├── tabs.jsx
│   │   │       ├── toast.jsx
│   │   │       └── ... (еще 36 компонентов)
│   │   │
│   │   ├── hooks/
│   │   │   └── use-toast.js   # Хук для уведомлений
│   │   │
│   │   └── lib/
│   │       └── utils.js       # Утилиты (cn helper)
│   │
│   ├── package.json           # Node.js зависимости
│   ├── tailwind.config.js     # Tailwind конфигурация
│   ├── postcss.config.js      # PostCSS конфигурация
│   └── .env                   # Frontend переменные
│       ├── REACT_APP_BACKEND_URL  # URL бэкенда
│       └── WDS_SOCKET_PORT        # WebSocket порт
│
├── tests/
│   └── __init__.py
│
├── AI_CONTEXT.md              # Этот файл
├── README.md                  # Документация проекта
└── test_result.md             # Результаты тестирования
```

---

## 🎨 Дизайн-система

### Цветовая палитра

```css
/* Основные цвета */
--bg-main: #1C1C1C;              /* Фон приложения */
--text-primary: #FFFFFF;          /* Основной текст */
--text-secondary: rgba(255, 255, 255, 0.7);  /* Вторичный текст */
--text-muted: #959595;            /* Приглушённый текст */
--accent-orange: #FF6B00;         /* Акцентный оранжевый */
--accent-gradient-start: #FF8A24; /* Градиент начало */
--accent-gradient-end: #FFDA24;   /* Градиент конец */

/* UI элементы */
--card-bg: #333333;               /* Фон карточек */
--progress-bg: #FFEBD9;           /* Фон progress ring */
--progress-fill: #FF8A24;         /* Заливка progress ring */
```

### Типографика

| Шрифт | Вес | Использование |
|-------|-----|---------------|
| Plus Jakarta Sans | 700 (Bold) | Заголовки, числа |
| Plus Jakarta Sans | 500 (Medium) | Основной текст |
| SF Pro Display | - | Системный fallback |

### Размеры (Mobile-first)

```css
/* Базовые размеры (Mobile ~430px) */
Header padding: 16px 30px (top: 40px)
Logo: 90x56px
Avatar: 40x40px
Menu icon: 40x40px
Greeting font: 21px
Streak icon: 16x16px
Streak font: 14px
Day card: 72x100px
Day card radius: 24px
```

### Визуальные эффекты

1. **Градиент header:** `filter: blur(100px)` создаёт мягкое свечение
2. **Выделенный день:** `linear-gradient(-34deg, #FF8A24, #FFDA24)`
3. **Progress ring:** SVG с анимированным `stroke-dashoffset`

---

## 🔧 Текущие компоненты

### 1. Header
- **Логотип** (TWBlogo.png) — слева
- **Кнопка меню** (menu.svg) — справа, без функционала
- **Аватар пользователя** — загружается из Telegram или fallback на UI Avatars

### 2. Приветствие
- Динамический текст по времени суток
- Иконка справа от текста (24x24px)
- Fallback имени: "Гость"

| Время | Приветствие | Иконка |
|-------|-------------|--------|
| 05:00-11:59 | Доброе утро | sunrise.svg |
| 12:00-17:59 | Добрый день | day.svg |
| 18:00-22:59 | Добрый вечер | sunset.svg |
| 23:00-04:59 | Доброй ночи | night.svg |

### 3. Тренировочная серия (Streak)
- Иконка огня (fire_strike.svg)
- Текст: "Тренировочная серия в течение X дней"
- Пока статично 0 дней

### 4. DateSelector (Выбор дня)
- Горизонтальный scroll с днями недели
- Карточки с progress ring (0-100%)
- Выделение выбранного дня градиентом
- Данные прогресса пока mock (MOCK_PROGRESS)

---

## 📡 API Endpoints

### Текущие endpoints

```
GET  /api/        — Health check, возвращает {"message": "Hello World"}
POST /api/status  — Создание StatusCheck записи
GET  /api/status  — Получение всех StatusCheck записей
```

### Модели данных

```python
class StatusCheck:
    id: str          # UUID
    client_name: str
    timestamp: datetime
```

---

## 📱 Telegram интеграция

### Инициализация
```javascript
if (window.Telegram?.WebApp) {
  const tg = window.Telegram.WebApp;
  tg.ready();   // Сигнал о готовности
  tg.expand();  // Развернуть на весь экран
}
```

### Доступные данные пользователя
```javascript
window.Telegram.WebApp.initDataUnsafe.user:
- id
- first_name
- last_name
- username
- photo_url
- language_code
```

### Fallback для аватара
```
https://ui-avatars.com/api/?name={first_name}&background=FF6B00&color=fff&size=80
```

---

## ⚠️ Важные правила для AI агентов

### ❌ НЕ ДЕЛАТЬ

1. **НЕ использовать npm** — только `yarn`
2. **НЕ хардкодить URLs** — брать из .env
3. **НЕ использовать MongoDB ObjectID** — только UUID
4. **НЕ запускать uvicorn напрямую** — использовать supervisor
5. **НЕ модифицировать .env URLs/ports**
6. **НЕ использовать `create_file overwrite=True`** для существующих файлов

### ✅ ДЕЛАТЬ

1. **Все API routes** должны начинаться с `/api`
2. **MongoDB ответы** — исключать `_id`, использовать `{"_id": 0}`
3. **После изменения .env** — перезапустить сервисы
4. **Новые пакеты** — добавлять в requirements.txt/package.json
5. **Использовать search_replace** для редактирования файлов
6. **Hot reload** работает для кода, не для .env

---

## 🚀 Команды разработки

### Установка зависимостей
```bash
# Frontend
cd /app/frontend && yarn add [package]

# Backend
cd /app/backend && pip install [package]
echo "[package]==[version]" >> requirements.txt
```

### Перезапуск сервисов
```bash
sudo supervisorctl restart frontend
sudo supervisorctl restart backend
sudo supervisorctl restart all
```

### Логи
```bash
# Backend логи
tail -n 100 /var/log/supervisor/backend.err.log
tail -n 100 /var/log/supervisor/backend.out.log

# Frontend логи
tail -n 100 /var/log/supervisor/frontend.err.log
tail -n 100 /var/log/supervisor/frontend.out.log
```

### Статус сервисов
```bash
sudo supervisorctl status
```

---

## 📋 Планируемые функции (Backlog)

### Высокий приоритет
- [ ] Регистрация пользователя с выбором тренировочного плана
- [ ] API для тренировочных планов и упражнений
- [ ] Главный экран с днями недели и списком упражнений
- [ ] Карточки упражнений (название, подходы, повторы, вес)

### Средний приоритет
- [ ] Отметка выполнения упражнений
- [ ] Таймер отдыха между подходами
- [ ] Профиль пользователя
- [ ] Меню навигации (Sheet/Drawer)

### Низкий приоритет
- [ ] Статистика прогресса с графиками
- [ ] Уведомления о тренировках
- [ ] Экспорт данных
- [ ] Настройки приложения

---

## 🔄 История изменений

| Дата | Версия | Изменения |
|------|--------|-----------|
| Янв 2025 | 1.0 | Начальная версия, Header, DateSelector |
| Июль 2025 | 2.0 | Обновлена документация AI_CONTEXT.md |

---

## 📚 Дополнительные ресурсы

- [Telegram WebApp API](https://core.telegram.org/bots/webapps)
- [Shadcn/UI Docs](https://ui.shadcn.com/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Motor Docs](https://motor.readthedocs.io/)
