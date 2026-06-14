import React, { useState, useMemo, useEffect } from 'react';
import { Zap } from 'lucide-react';
import './DateSelector.css';

// Сокращённые названия дней недели
const DAY_NAMES = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

// Тестовые данные прогресса тренировок (0-100%)
const MOCK_PROGRESS = {
  0: 100, // Воскресенье
  1: 75,  // Понедельник
  2: 50,  // Вторник
  3: 0,   // Среда
  4: 25,  // Четверг
  5: 0,   // Пятница
  6: 0,   // Суббота
};

// Тестовые данные статистики тренировки (пока мок, не из БД)
const WORKOUT_STATS = [
  { value: '4600кг', label: 'Тоннаж' },
  { value: 'Н+Г+С', label: 'Группа' },
  { value: 'Тяжело', label: 'Сложность' },
  { value: '2ч. 16м.', label: 'Время' },
];

// Компонент кругового прогресс-бара
const ProgressRing = ({ progress, size = 50, strokeWidth = 4, isSelected = false, index = 0 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // Анимация заполнения при загрузке: стартуем с 0% и плавно заполняем до целевого значения
  const [animatedProgress, setAnimatedProgress] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedProgress(progress), 60);
    return () => clearTimeout(timer);
  }, [progress]);

  const strokeDashoffset = circumference - (animatedProgress / 100) * circumference;

  return (
    <svg 
      className="progress-ring" 
      viewBox={`0 0 ${size} ${size}`}
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Фоновый круг - скрываем при выборе */}
      <circle
        className="progress-ring-bg"
        cx={size / 2}
        cy={size / 2}
        r={radius}
        strokeWidth={strokeWidth}
        fill={isSelected ? "transparent" : "#1C1C1C"}
        style={{ stroke: (progress > 0 || isSelected) ? "rgba(255, 235, 217, 0.6)" : "#1C1C1C" }}
      />
      {/* Прогресс */}
      <circle
        className="progress-ring-progress"
        cx={size / 2}
        cy={size / 2}
        r={radius}
        strokeWidth={strokeWidth}
        fill="transparent"
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{
          transition: 'stroke-dashoffset 0.9s cubic-bezier(0.22, 1, 0.36, 1)',
          transitionDelay: `${index * 90}ms`,
        }}
      />
    </svg>
  );
};

// Компонент карточки дня
const DayCard = ({ date, dayName, dayNumber, progress, isSelected, onClick, index = 0, animClass = '' }) => {
  return (
    <button 
      className={`day-card ${isSelected ? 'day-card-selected' : ''} ${animClass}`}
      onClick={onClick}
      aria-label={`${dayName}, ${dayNumber} число`}
      aria-pressed={isSelected}
      style={animClass ? { animationDelay: `${index * 55}ms` } : undefined}
    >
      <span className="day-card-name">{dayName}</span>
      <div className="day-card-circle-wrapper">
        <ProgressRing progress={progress} isSelected={isSelected} index={index} />
        <span className="day-card-number">{dayNumber}</span>
      </div>
    </button>
  );
};

// Основной компонент выбора даты
// Названия месяцев в родительном падеже
const MONTH_NAMES = [
  'Января', 'Февраля', 'Марта', 'Апреля', 'Мая', 'Июня',
  'Июля', 'Августа', 'Сентября', 'Октября', 'Ноября', 'Декабря'
];

// Доступные тренировочные недели (смещения относительно текущей, 0 = текущая)
const WEEK_OFFSETS = [-1, 0, 1];

const DateSelector = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [weekOffset, setWeekOffset] = useState(0); // Смещение недели (0 = текущая)
  const [slideDir, setSlideDir] = useState(null); // Направление анимации смены недели: 'next' | 'prev' | null
  
  // Генерируем дни недели с учётом смещения
  const weekDays = useMemo(() => {
    const today = new Date();
    const currentDay = today.getDay(); // 0 = Воскресенье
    
    // Начало недели (Понедельник) с учётом смещения
    const monday = new Date(today);
    monday.setDate(today.getDate() - ((currentDay + 6) % 7) + (weekOffset * 7));
    
    const days = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(monday);
      date.setDate(monday.getDate() + i);
      
      const dayOfWeek = date.getDay();
      days.push({
        date: date,
        dayName: DAY_NAMES[dayOfWeek],
        dayNumber: date.getDate(),
        progress: MOCK_PROGRESS[dayOfWeek] || 0,
      });
    }
    
    return days;
  }, [weekOffset]);
  
  const handleDayClick = (date, event) => {
    setSelectedDate(date);
    // Автоматический скролл к выбранной карточке дня
    if (event?.currentTarget) {
      event.currentTarget.scrollIntoView({
        behavior: 'smooth',
        inline: 'center',
        block: 'nearest',
      });
    }
  };
  
  const handleWeekDotClick = (offset) => {
    if (offset === weekOffset) return;
    // Направление: вперёд (следующая) — выезд справа, назад (прошлая) — слева
    setSlideDir(offset > weekOffset ? 'next' : 'prev');
    setWeekOffset(offset);
  };
  
  const isSameDay = (date1, date2) => {
    return date1.getDate() === date2.getDate() &&
           date1.getMonth() === date2.getMonth() &&
           date1.getFullYear() === date2.getFullYear();
  };
  
  // Форматирование выбранной даты
  const formattedDate = `${selectedDate.getDate()} ${MONTH_NAMES[selectedDate.getMonth()]}`;
  
  return (
    <div className="date-selector" data-testid="date-selector">
      <div className="date-selector-row">
        {/* Индикатор-точки: вертикально, слева от кнопок */}
        <div
          className="week-dots"
          role="tablist"
          aria-label="Выбор тренировочной недели"
          data-testid="week-dots"
        >
          {WEEK_OFFSETS.map((offset) => {
            const isActive = weekOffset === offset;
            const label =
              offset === 0
                ? 'Текущая неделя'
                : offset > 0
                ? `Через ${offset} нед.`
                : `${Math.abs(offset)} нед. назад`;
            return (
              <button
                key={offset}
                type="button"
                className={`week-dot ${isActive ? 'week-dot-active' : ''}`}
                onClick={() => handleWeekDotClick(offset)}
                role="tab"
                aria-selected={isActive}
                aria-label={label}
                data-testid={`week-dot-${offset}`}
              />
            );
          })}
        </div>

        {/* Дни недели — горизонтальный скролл (не перекрывает точки) */}
        <div className="date-selector-scroll" data-testid="date-selector-scroll">
          {weekDays.map((day, index) => (
            <DayCard
              key={`${weekOffset}-${index}`}
              date={day.date}
              dayName={day.dayName}
              dayNumber={day.dayNumber}
              progress={day.progress}
              isSelected={isSameDay(day.date, selectedDate)}
              onClick={(e) => handleDayClick(day.date, e)}
              index={index}
              animClass={
                slideDir === 'next'
                  ? 'card-anim-next'
                  : slideDir === 'prev'
                  ? 'card-anim-prev'
                  : ''
              }
            />
          ))}
        </div>
      </div>

      <div className="date-title-row">
        <h2 className="selected-date-title">{formattedDate}</h2>
        <button
          className="launch-button"
          type="button"
          data-testid="launch-button"
        >
          <Zap className="launch-button-icon" size={16} strokeWidth={2.5} />
          <span>Запустить</span>
        </button>
      </div>

      {/* Статистика тренировки (мок-данные) */}
      <div className="workout-stats" data-testid="workout-stats">
        {WORKOUT_STATS.map((stat) => (
          <div className="workout-stat" key={stat.label}>
            <span className="workout-stat-value">{stat.value}</span>
            <span className="workout-stat-label">{stat.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DateSelector;
