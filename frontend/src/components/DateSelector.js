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
const ProgressRing = ({ progress, size = 43, strokeWidth = 3 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (progress / 100) * circumference;
  
  return (
    <svg 
      className="progress-ring" 
      width={size} 
      height={size}
      viewBox={`0 0 ${size} ${size}`}
    >
      {/* Фоновый круг */}
      <circle
        className="progress-ring-bg"
        cx={size / 2}
        cy={size / 2}
        r={radius}
        strokeWidth={strokeWidth}
        fill="#1C1C1C"
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
        <ProgressRing progress={progress} />
        <span className="day-card-number">{dayNumber}</span>
      </div>
    </button>
  );
};

// Основной компонент выбора даты
const DateSelector = () => {
  const [selectedDate, setSelectedDate] = useState(new Date());
  
  // Генерируем дни текущей недели
  const weekDays = useMemo(() => {
    const today = new Date();
    const currentDay = today.getDay(); // 0 = Воскресенье
    
    // Начало недели (Понедельник)
    const monday = new Date(today);
    monday.setDate(today.getDate() - ((currentDay + 6) % 7));
    
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
  }, []);
  
  const handleDayClick = (date) => {
    setSelectedDate(date);
  };
  
  const isSameDay = (date1, date2) => {
    return date1.getDate() === date2.getDate() &&
           date1.getMonth() === date2.getMonth() &&
           date1.getFullYear() === date2.getFullYear();
  };
  
  return (
    <div className="date-selector" data-testid="date-selector">
      <div className="date-selector-scroll">
        {weekDays.map((day, index) => (
          <DayCard
            key={index}
            date={day.date}
            dayName={day.dayName}
            dayNumber={day.dayNumber}
            progress={day.progress}
            isSelected={isSameDay(day.date, selectedDate)}
            onClick={() => handleDayClick(day.date)}
          />
        ))}
      </div>
    </div>
  );
};

export default DateSelector;
