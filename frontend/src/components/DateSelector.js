import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Zap, Pause, Play, Square, Bolt, WandSparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { useUser } from '@/context/UserContext';
import {
  getActivePlan, getWeekProgress, getPlanDay,
  startSession, getActiveSession, sessionExerciseAction,
  editSessionExercise, finishSession, pauseSession,
} from '@/api';
import WorkoutView from '@/components/WorkoutView';
import './DateSelector.css';

// Сокращённые названия дней недели (index = JS getDay(): 0=Вс..6=Сб)
const DAY_NAMES = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];

// Преобразование JS getDay() (Вс=0..Сб=6) в day_index плана (Пн=1..Вс=7)
const toDayIndex = (jsDay) => ((jsDay + 6) % 7) + 1;

// Компонент кругового прогресс-бара
const ProgressRing = ({ progress, size = 50, strokeWidth = 4, isSelected = false, isWorkout = false, index = 0 }) => {
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
        style={{ stroke: (progress > 0 || isSelected || isWorkout) ? "rgba(255, 235, 217, 0.6)" : "#1C1C1C" }}
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
const DayCard = ({ date, dayName, dayNumber, progress, isSelected, isWorkout = false, onClick, index = 0, animClass = '' }) => {
  return (
    <button 
      className={`day-card ${isSelected ? 'day-card-selected' : ''} ${isWorkout ? 'day-card-workout' : ''} ${animClass}`}
      onClick={onClick}
      aria-label={`${dayName}, ${dayNumber} число${isWorkout ? ', тренировка' : ''}`}
      aria-pressed={isSelected}
      style={animClass ? { animationDelay: `${index * 55}ms` } : undefined}
    >
      <span className="day-card-name">{dayName}</span>
      <div className="day-card-circle-wrapper">
        <ProgressRing progress={progress} isSelected={isSelected} isWorkout={isWorkout} index={index} />
        <span className="day-card-number">{dayNumber}</span>
      </div>
      {isWorkout ? <span className="day-card-dot" aria-hidden="true" /> : null}
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
  const { user } = useUser();
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [weekOffset, setWeekOffset] = useState(0); // Смещение недели (0 = текущая)
  const [slideDir, setSlideDir] = useState(null); // Направление анимации смены недели

  const [plan, setPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(true);
  const [progressByDay, setProgressByDay] = useState({}); // day_index -> info
  const [dayDetail, setDayDetail] = useState(null);

  // Какая неделя плана соответствует отображаемому смещению
  const planWeek = useMemo(() => {
    if (!plan) return 1;
    const base = plan.current_week || 1;
    const total = (plan.weeks && plan.weeks.length) || 1;
    return Math.min(Math.max(1, base + weekOffset), total);
  }, [plan, weekOffset]);

  // Загрузка активного плана спортсмена
  useEffect(() => {
    if (!user?.telegram_id) return undefined;
    let cancelled = false;
    setPlanLoading(true);
    (async () => {
      try {
        const p = await getActivePlan(user.telegram_id);
        if (!cancelled) setPlan(p);
      } catch (e) {
        if (!cancelled) setPlan(null);
      } finally {
        if (!cancelled) setPlanLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user?.telegram_id]);

  // Загрузка прогресса по дням выбранной недели
  useEffect(() => {
    if (!plan?.id) { setProgressByDay({}); return undefined; }
    let cancelled = false;
    (async () => {
      try {
        const data = await getWeekProgress(plan.id, planWeek);
        if (cancelled) return;
        const map = {};
        (data.days || []).forEach((d) => { map[d.day_index] = d; });
        setProgressByDay(map);
      } catch (e) {
        if (!cancelled) setProgressByDay({});
      }
    })();
    return () => { cancelled = true; };
  }, [plan?.id, planWeek]);

  // Генерируем дни недели с учётом смещения
  const weekDays = useMemo(() => {
    const today = new Date();
    const currentDay = today.getDay(); // 0 = Воскресенье

    const monday = new Date(today);
    monday.setDate(today.getDate() - ((currentDay + 6) % 7) + (weekOffset * 7));

    const days = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(monday);
      date.setDate(monday.getDate() + i);

      const di = toDayIndex(date.getDay());
      const info = progressByDay[di];
      days.push({
        date: date,
        dayName: DAY_NAMES[date.getDay()],
        dayNumber: date.getDate(),
        progress: info?.progress_pct || 0,
        isWorkout: !!info?.is_workout,
      });
    }

    return days;
  }, [weekOffset, progressByDay]);

  // Загрузка деталей выбранного дня
  useEffect(() => {
    if (!plan?.id) { setDayDetail(null); return undefined; }
    const di = toDayIndex(selectedDate.getDay());
    let cancelled = false;
    (async () => {
      try {
        const d = await getPlanDay(plan.id, planWeek, di);
        if (!cancelled) setDayDetail(d);
      } catch (e) {
        if (!cancelled) setDayDetail(null);
      }
    })();
    return () => { cancelled = true; };
  }, [plan?.id, planWeek, selectedDate]);

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

  const isRestSelected = !dayDetail || dayDetail.is_rest;
  const selectedDayIndex = toDayIndex(selectedDate.getDay());

  // Тренировочная сессия выбранного дня
  const [session, setSession] = useState(null);
  const [starting, setStarting] = useState(false);

  const refreshProgress = useCallback(async () => {
    if (!plan?.id) return;
    try {
      const data = await getWeekProgress(plan.id, planWeek);
      const map = {};
      (data.days || []).forEach((d) => { map[d.day_index] = d; });
      setProgressByDay(map);
      window.dispatchEvent(new Event('twb:progress'));
    } catch (e) { /* no-op */ }
  }, [plan?.id, planWeek]);

  // Загрузка активной сессии выбранного дня
  useEffect(() => {
    if (!plan?.id || isRestSelected || !user?.telegram_id) { setSession(null); return undefined; }
    let cancelled = false;
    (async () => {
      try {
        const s = await getActiveSession({
          plan_id: plan.id, week: planWeek, day: selectedDayIndex, athlete: user.telegram_id,
        });
        if (!cancelled) setSession(s);
      } catch (e) {
        if (!cancelled) setSession(null);
      }
    })();
    return () => { cancelled = true; };
  }, [plan?.id, planWeek, selectedDayIndex, isRestSelected, user?.telegram_id]);

  // Превью дня (до старта тренировки)
  const previewView = useMemo(() => {
    if (!dayDetail || dayDetail.is_rest) return null;
    const exs = (dayDetail.exercises || []).map((e) => ({ ...e, status: 'pending' }));
    const tonnage = exs.reduce((s, e) => s + (Number(e.tonnage) || 0), 0);
    const estSec = exs.reduce((s, e) => {
      const sets = (e.sets_scheme || []).reduce((a, x) => a + (Number(x.sets) || 0), 0);
      return s + sets * 130;
    }, 0);
    return {
      status: 'not_started',
      title: dayDetail.title,
      exercises: exs,
      stats: {
        tonnage: Math.round(tonnage),
        group: dayDetail.group,
        difficulty: dayDetail.difficulty,
        duration_sec: estSec,
        done_count: 0,
        total_count: exs.length,
        progress_pct: 0,
      },
    };
  }, [dayDetail]);

  const view = session || previewView;

  const handleStart = async () => {
    if (!plan) { toast.info('Сначала выберите программу'); return; }
    if (isRestSelected) { toast.info('Сегодня день отдыха 💤'); return; }
    setStarting(true);
    try {
      const s = await startSession({
        plan_id: plan.id, athlete_telegram_id: user.telegram_id,
        week: planWeek, day: selectedDayIndex,
      });
      setSession(s);
      refreshProgress();
    } catch (e) {
      toast.error('Не удалось начать тренировку');
    } finally {
      setStarting(false);
    }
  };

  const handleAction = async (order, action) => {
    if (!session) return;
    try {
      const s = await sessionExerciseAction(session.id, order, action);
      setSession(s);
      refreshProgress();
      if (s.status === 'finished') toast.success('Тренировка завершена! 🎉');
    } catch (e) {
      toast.error('Не удалось обновить упражнение');
    }
  };

  const handleEditSave = async (order, body) => {
    if (!session) return;
    try {
      const s = await editSessionExercise(session.id, order, body);
      setSession(s);
      toast.success('Упражнение обновлено');
    } catch (e) {
      toast.error('Не удалось сохранить');
    }
  };

  const handlePauseToggle = async () => {
    if (!session) return;
    try {
      const s = await pauseSession(session.id, session.paused);
      setSession(s);
    } catch (e) { /* no-op */ }
  };

  const handleStop = async () => {
    if (!session) return;
    try {
      const s = await finishSession(session.id);
      setSession(s);
      refreshProgress();
      toast.success('Тренировка завершена');
    } catch (e) { /* no-op */ }
  };

  const sessionStatus = session?.status;

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
              isWorkout={day.isWorkout}
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
        <div className="date-actions" data-testid="date-actions">
          {sessionStatus === 'in_progress' ? (
            <>
              <button className="icon-btn" type="button" onClick={handlePauseToggle}
                aria-label={session.paused ? 'Продолжить' : 'Пауза'} data-testid="btn-pause">
                {session.paused ? <Play size={18} strokeWidth={2.2} color="#CACACA" /> : <Pause size={18} strokeWidth={2.2} color="#CACACA" />}
              </button>
              <button className="icon-btn" type="button" onClick={handleStop}
                aria-label="Завершить" data-testid="btn-stop">
                <Square size={15} strokeWidth={2.6} color="#CACACA" />
              </button>
              <button className="icon-btn" type="button"
                onClick={() => toast.info('Настройки тренировки скоро')}
                aria-label="Настройки" data-testid="btn-settings">
                <Bolt size={18} strokeWidth={2.2} color="#CACACA" />
              </button>
            </>
          ) : sessionStatus === 'finished' ? (
            <>
              <button className="icon-btn" type="button"
                onClick={() => toast.info('Настройки тренировки скоро')}
                aria-label="Настройки" data-testid="btn-settings">
                <Bolt size={18} strokeWidth={2.2} color="#CACACA" />
              </button>
              <button className="icon-btn" type="button"
                onClick={() => toast.info('Нажмите ✨ на упражнении, чтобы изменить его')}
                aria-label="Изменить" data-testid="btn-edit">
                <WandSparkles size={18} />
              </button>
            </>
          ) : !isRestSelected ? (
            <button
              className="launch-button"
              type="button"
              data-testid="launch-button"
              onClick={handleStart}
              disabled={!plan || starting}
            >
              <Zap className="launch-button-icon" size={16} strokeWidth={2.5} />
              <span>{starting ? 'Запуск…' : 'Начать'}</span>
            </button>
          ) : null}
        </div>
      </div>

      {/* Нет активной программы */}
      {!planLoading && !plan ? (
        <div className="no-plan-card" data-testid="no-plan-card">
          <p className="no-plan-text">У вас пока нет активной программы.</p>
          <Link to="/programs" className="no-plan-button" data-testid="choose-program-button">
            Выбрать программу
          </Link>
        </div>
      ) : null}

      {/* День отдыха */}
      {plan && isRestSelected ? (
        <div className="rest-day-note" data-testid="rest-day-note">
          День отдыха — восстановление 💤
        </div>
      ) : null}

      {/* Тренировка дня */}
      {plan && !isRestSelected && view ? (
        <WorkoutView
          view={view}
          isPreview={!session}
          paused={!!session?.paused}
          onAction={handleAction}
          onEditSave={handleEditSave}
        />
      ) : null}
    </div>
  );
};

export default DateSelector;
