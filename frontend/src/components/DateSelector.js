import React, { useState, useMemo } from 'react';
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

// Компонент кругового прогресс-бара
const ProgressRing = ({ progress, size = 50, strokeWidth = 4, isSelected = false }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (progress / 100) * circumference;
  
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
      />
    </svg>
  );
};

// Компонент карточки дня
const DayCard = ({ date, dayName, dayNumber, progress, isSelected, onClick }) => {
  return (
    <button 
      className={`day-card ${isSelected ? 'day-card-selected' : ''}`}
      onClick={onClick}
      aria-label={`${dayName}, ${dayNumber} число`}
      aria-pressed={isSelected}
    >
      <span className="day-card-name">{dayName}</span>
      <div className="day-card-circle-wrapper">
        <ProgressRing progress={progress} isSelected={isSelected} />
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

const DateSelector = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [weekOffset, setWeekOffset] = useState(0); // Смещение недели (0 = текущая)
  
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
  
  const handleDayClick = (date) => {
    setSelectedDate(date);
  };
  
  const handlePrevWeek = () => {
    setWeekOffset(prev => prev - 1);
  };
  
  const handleNextWeek = () => {
    setWeekOffset(prev => prev + 1);
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
        {/* Кнопка предыдущей недели */}
        <button 
          className="week-nav-button"
          onClick={handlePrevWeek}
          aria-label="Предыдущая неделя"
          data-testid="prev-week-button"
        >
          <img src="/arrow-left.svg" alt="Назад" />
        </button>
        
        {/* Дни недели */}
        <div className="date-selector-scroll">
          {weekDays.map((day, index) => (
            <DayCard
              key={`${weekOffset}-${index}`}
              date={day.date}
              dayName={day.dayName}
              dayNumber={day.dayNumber}
              progress={day.progress}
              isSelected={isSameDay(day.date, selectedDate)}
              onClick={() => handleDayClick(day.date)}
            />
          ))}
        </div>
        
        {/* Кнопка следующей недели */}
        <button 
          className="week-nav-button"
          onClick={handleNextWeek}
          aria-label="Следующая неделя"
          data-testid="next-week-button"
        >
          <img src="/arrow-right.svg" alt="Вперёд" />
        </button>
      </div>
      
      <h2 className="selected-date-title">{formattedDate}</h2>
    </div>
  );
};

export default DateSelector;
