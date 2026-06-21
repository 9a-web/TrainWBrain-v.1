import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Flame, Gift, Check, Trophy, Dumbbell, Target } from "lucide-react";
import { useUser } from "@/context/UserContext";
import { useBackButton } from "@/hooks/useTelegramUI";
import { getStreakData } from "@/api";
import "./Streak.css";

const WD = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const pluralize = (n, forms) => {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
};

function DayCircle({ d }) {
  let cls = "sk-circle";
  if (d.trained) cls += " is-done";
  else if (d.is_today) cls += " is-today";
  else if (d.is_future) cls += " is-future";
  else cls += " is-miss";
  return (
    <div className="sk-day" data-testid={`sk-day-${d.weekday}`}>
      <span className="sk-day-label">{WD[d.weekday - 1]}</span>
      <span className={cls}>
        {d.trained ? <Check size={20} strokeWidth={3} /> : null}
        {!d.trained && d.is_today ? <i className="sk-today-dot" /> : null}
      </span>
    </div>
  );
}

export default function StreakPage() {
  const { user } = useUser();
  const navigate = useNavigate();
  const tg = user?.telegram_id;
  useBackButton(true, () => navigate(-1));

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tg) return undefined;
    let alive = true;
    setLoading(true);
    getStreakData(tg, { weeks: 12 })
      .then((d) => { if (alive) setData(d); })
      .catch(() => { if (alive) setData(null); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [tg]);

  const cur = data?.current_streak || 0;
  const best = data?.best_streak || 0;
  const total = data?.total_workouts || 0;
  const goal = data?.weekly_goal || 0;
  const thisWeek = data?.trained_this_week || 0;
  const weekDays = data?.week?.days || [];
  const calendar = data?.calendar || [];
  const rewardActive = goal > 0 && thisWeek >= goal;

  return (
    <div className="sk-page" data-testid="streak-page">
      <header className="sk-header">
        <button className="sk-back" onClick={() => navigate(-1)} aria-label="Назад" data-testid="streak-back">
          <ArrowLeft size={22} />
        </button>
        <h1 className="sk-title">Тренировочная серия</h1>
      </header>

      {loading ? (
        <div className="sk-loading"><div className="sk-spinner" /></div>
      ) : (
        <>
          {/* Hero */}
          <div className="sk-hero" data-testid="streak-hero">
            <div className="sk-hero-glow" />
            <div className={`sk-flame ${cur > 0 ? "lit" : ""}`}>
              <Flame size={40} strokeWidth={2} />
            </div>
            <div className="sk-num" data-testid="streak-current">{cur}</div>
            <div className="sk-num-label">
              {pluralize(cur, ["день", "дня", "дней"])} подряд
            </div>
            <div className="sk-substats">
              <div className="sk-sub">
                <Trophy size={15} />
                <b>{best}</b>
                <span>рекорд</span>
              </div>
              <div className="sk-sub">
                <Dumbbell size={15} />
                <b>{total}</b>
                <span>тренировок</span>
              </div>
              <div className="sk-sub">
                <Target size={15} />
                <b>{goal ? `${thisWeek}/${goal}` : thisWeek}</b>
                <span>за неделю</span>
              </div>
            </div>
          </div>

          {/* Эта неделя */}
          <section className="sk-card" data-testid="streak-week">
            <div className="sk-card-head">
              <h3 className="sk-card-title">Эта неделя</h3>
              {goal ? (
                <span className="sk-card-hint">цель {goal} в неделю</span>
              ) : null}
            </div>
            <div className="sk-week">
              {weekDays.map((d) => (
                <DayCircle key={d.date} d={d} />
              ))}
              <div className="sk-day sk-reward" data-testid="streak-reward">
                <span className="sk-day-label">Приз</span>
                <span className={`sk-gift ${rewardActive ? "active" : ""}`}>
                  <Gift size={20} strokeWidth={2.2} />
                </span>
              </div>
            </div>
            {goal ? (
              <p className="sk-reward-note">
                {rewardActive
                  ? "Цель недели выполнена — так держать! 🎉"
                  : `Ещё ${goal - thisWeek} ${pluralize(goal - thisWeek, ["тренировка", "тренировки", "тренировок"])} до награды за неделю`}
              </p>
            ) : null}
          </section>

          {/* История (хитмап) */}
          <section className="sk-card" data-testid="streak-history">
            <div className="sk-card-head">
              <h3 className="sk-card-title">История</h3>
              <span className="sk-card-hint">последние {calendar.length} нед.</span>
            </div>
            <div className="sk-heatmap-wrap">
              <div className="sk-hm-labels">
                {WD.map((w) => (
                  <span key={w} className="sk-hm-label">{w}</span>
                ))}
              </div>
              <div className="sk-heatmap" data-testid="streak-heatmap">
                {calendar.map((wk) => (
                  <div className="sk-hm-week" key={wk.week_start}>
                    {wk.days.map((d) => {
                      let cls = "sk-hm-cell";
                      if (d.trained) cls += " done";
                      else if (d.is_future) cls += " future";
                      else if (d.is_today) cls += " today";
                      return <span key={d.date} className={cls} title={d.date} />;
                    })}
                  </div>
                ))}
              </div>
            </div>
            <div className="sk-hm-legend">
              <span>меньше</span>
              <i className="sk-hm-cell" />
              <i className="sk-hm-cell done dim" />
              <i className="sk-hm-cell done" />
              <span>больше</span>
            </div>
          </section>

          {total === 0 ? (
            <p className="sk-empty-note" data-testid="streak-empty">
              Заверши первую тренировку — и серия начнётся 🔥
            </p>
          ) : null}

          <div className="sk-foot" />
        </>
      )}
    </div>
  );
}
