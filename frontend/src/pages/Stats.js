import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft, Dumbbell, Flame, CalendarDays, Target, Layers, Clock,
  TrendingUp, ChevronDown, Activity, Trophy, CheckCircle2, XCircle,
  PauseCircle, ShieldCheck, CalendarClock,
} from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { useUser } from "@/context/UserContext";
import { useBackButton } from "@/hooks/useTelegramUI";
import {
  getActivePlan, getCoachClientPlan, getUserById,
  getDetailedStats, getExerciseProgress,
  getCoachClientStats, getCoachClientExerciseProgress,
} from "@/api";
import "./Stats.css";

const PIE_COLORS = ["#FF8A24", "#FFC24B", "#36C5F0", "#A78BFA", "#34D399", "#FB7185"];

const fmtTon = (kg) => {
  const n = Number(kg) || 0;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)} т`;
  return `${Math.round(n)} кг`;
};
const fmtDur = (s) => {
  const m = Math.round((Number(s) || 0) / 60);
  if (m < 1) return "—";
  if (m < 60) return `${m} мин`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} ч ${r} мин` : `${h} ч`;
};
const shortWeek = (w) => (typeof w === "string" ? w.replace(/^\d{4}-W/, "W") : w);
const avatarFallback = (name) =>
  `https://ui-avatars.com/api/?name=${encodeURIComponent(name || "U")}&background=FF6B00&color=fff&size=96&bold=true`;

const SKIP_META = {
  completed: { label: "Выполнено", color: "#34D399", Icon: CheckCircle2 },
  missed: { label: "Пропущено", color: "#FB7185", Icon: XCircle },
  skipped: { label: "Скип", color: "#FFC24B", Icon: PauseCircle },
  excused: { label: "Уважит.", color: "#36C5F0", Icon: ShieldCheck },
  rescheduled: { label: "Перенос", color: "#A78BFA", Icon: CalendarClock },
};

function ChartTooltip({ active, payload, label, unit }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="stats-tt">
      <div className="stats-tt-label">{label}</div>
      {payload.map((p) => (
        <div className="stats-tt-row" key={p.dataKey || p.name}>
          <span className="stats-tt-dot" style={{ background: p.color || p.stroke || p.fill }} />
          <span className="stats-tt-name">{p.name}</span>
          <b className="stats-tt-val">
            {typeof p.value === "number" ? p.value.toLocaleString("ru-RU") : p.value}
            {unit ? ` ${unit}` : ""}
          </b>
        </div>
      ))}
    </div>
  );
}

function KpiCard({ icon: Icon, value, label, accent, testid }) {
  return (
    <div className="stats-kpi" data-testid={testid}>
      <span className="stats-kpi-ic" style={accent ? { color: accent } : undefined}>
        <Icon size={18} />
      </span>
      <span className="stats-kpi-val">{value}</span>
      <span className="stats-kpi-label">{label}</span>
    </div>
  );
}

function SectionCard({ title, hint, action, children, testid }) {
  return (
    <section className="stats-card" data-testid={testid}>
      {(title || action) && (
        <div className="stats-card-head">
          <div className="stats-card-titles">
            <h3 className="stats-card-title">{title}</h3>
            {hint ? <span className="stats-card-hint">{hint}</span> : null}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

function StatsView({ name, avatar, subtitle, onBack, hasPlanFetch, fetchPlanId, fetchDetailed, fetchProgress }) {
  const [scope, setScope] = useState("plan"); // 'plan' | 'all'
  const [planId, setPlanId] = useState(undefined); // undefined=loading, null=none
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(null);
  const [selectedSlug, setSelectedSlug] = useState(null);

  useEffect(() => {
    let alive = true;
    fetchPlanId()
      .then((id) => alive && setPlanId(id || null))
      .catch(() => alive && setPlanId(null));
    return () => { alive = false; };
  }, [fetchPlanId]);

  const planParams = useMemo(
    () => (scope === "plan" && planId ? { plan_id: planId } : {}),
    [scope, planId]
  );

  useEffect(() => {
    if (planId === undefined) return undefined;
    let alive = true;
    setLoading(true);
    fetchDetailed(planParams)
      .then((d) => { if (alive) setData(d); })
      .catch(() => { if (alive) setData(null); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [planId, planParams, fetchDetailed]);

  useEffect(() => {
    if (planId === undefined) return undefined;
    let alive = true;
    const params = { ...planParams };
    if (selectedSlug) params.slug = selectedSlug;
    fetchProgress(params)
      .then((p) => {
        if (!alive) return;
        setProgress(p);
        if (!selectedSlug && p?.slug) setSelectedSlug(p.slug);
      })
      .catch(() => { if (alive) setProgress(null); });
    return () => { alive = false; };
  }, [planId, planParams, selectedSlug, fetchProgress]);

  const switchScope = (s) => {
    if (s === scope) return;
    setScope(s);
    setSelectedSlug(null);
    setProgress(null);
  };

  const summary = data?.summary || {};
  const empty = !loading && (!data || (summary.total_workouts || 0) === 0);

  const tonnage = data?.tonnage_by_week || [];
  const frequency = data?.frequency_by_week || [];
  const muscles = data?.muscle_distribution || [];
  const orm = data?.one_rep_max_est || [];
  const adherence = data?.adherence || {};
  const skipCounts = data?.skip_counts || {};
  const recent = data?.recent_sessions || [];
  const series = progress?.series || [];
  const exercises = progress?.exercises || [];

  const totalMuscleSets = muscles.reduce((a, m) => a + (m.sets || 0), 0);

  return (
    <div className="stats-page" data-testid="stats-page">
      <header className="stats-header">
        <button className="stats-back" onClick={onBack} aria-label="Назад" data-testid="stats-back">
          <ArrowLeft size={22} />
        </button>
        <div className="stats-head-id">
          <img className="stats-head-ava" src={avatar || avatarFallback(name)} alt="" />
          <div className="stats-head-text">
            <h1 className="stats-title">{name}</h1>
            <span className="stats-subtitle">{subtitle}</span>
          </div>
        </div>
      </header>

      {planId ? (
        <div className="stats-scope" data-testid="stats-scope">
          <button
            className={`stats-scope-btn ${scope === "plan" ? "active" : ""}`}
            onClick={() => switchScope("plan")}
            data-testid="scope-plan"
          >
            По плану
          </button>
          <button
            className={`stats-scope-btn ${scope === "all" ? "active" : ""}`}
            onClick={() => switchScope("all")}
            data-testid="scope-all"
          >
            Всё время
          </button>
        </div>
      ) : null}

      {loading ? (
        <div className="stats-loading" data-testid="stats-loading">
          <div className="stats-spinner" />
          <span>Считаем статистику…</span>
        </div>
      ) : empty ? (
        <div className="stats-empty" data-testid="stats-empty">
          <Activity size={34} />
          <p className="stats-empty-title">Пока нет завершённых тренировок</p>
          <p className="stats-empty-sub">
            Заверши хотя бы одну тренировку — здесь появятся тоннаж, прогресс и графики.
          </p>
        </div>
      ) : (
        <>
          {/* KPI */}
          <div className="stats-kpis" data-testid="stats-kpis">
            <KpiCard icon={Dumbbell} value={summary.total_workouts || 0} label="тренировок" testid="kpi-workouts" />
            <KpiCard icon={Flame} value={summary.workout_streak ?? summary.streak_days ?? 0} label="серия" accent="#FF8A24" testid="kpi-streak" />
            <KpiCard icon={CalendarDays} value={summary.avg_per_week || 0} label="в неделю" testid="kpi-freq" />
            <KpiCard icon={Target} value={`${summary.completion_pct || 0}%`} label="выполнение" testid="kpi-completion" />
            <KpiCard icon={Layers} value={fmtTon(summary.total_tonnage)} label="общий тоннаж" testid="kpi-tonnage" />
            <KpiCard icon={Clock} value={fmtDur(summary.total_duration_sec)} label="в зале" testid="kpi-duration" />
          </div>

          {/* 1ПМ по плану */}
          {orm.length ? (
            <SectionCard title="Одноповторный максимум" hint="по плану · факт" testid="stats-orm">
              <div className="stats-orm-grid">
                {orm.map((l) => {
                  const main = l.planned ?? l.achieved;
                  return (
                    <div className="stats-orm-card" key={l.lift} data-testid={`orm-${l.lift}`}>
                      <Trophy size={16} className="stats-orm-ic" />
                      <div className="stats-orm-name">{l.name}</div>
                      <div className="stats-orm-val">{main != null ? `${main}` : "—"}<span>кг</span></div>
                      <div className="stats-orm-sub">
                        {l.achieved != null ? <>факт <b>{l.achieved}</b></> : "—"}
                        {l.top_weight != null ? <span className="stats-orm-top"> · топ {l.top_weight}</span> : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </SectionCard>
          ) : null}

          {/* Тоннаж по неделям */}
          <SectionCard title="Тоннаж" hint={scope === "plan" ? "по микроциклам" : "по неделям"} testid="stats-tonnage-chart">
            {tonnage.length ? (
              <div className="stats-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tonnage} margin={{ top: 8, right: 4, left: -18, bottom: 0 }}>
                    <defs>
                      <linearGradient id="tonGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#FFDA24" />
                        <stop offset="100%" stopColor="#FF8A24" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="week" tickFormatter={shortWeek} tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} axisLine={false} tickLine={false} width={44} tickFormatter={(v) => (v >= 1000 ? `${Math.round(v / 1000)}т` : v)} />
                    <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} content={<ChartTooltip unit="кг" />} />
                    <Bar dataKey="tonnage" name="Тоннаж" fill="url(#tonGrad)" radius={[6, 6, 0, 0]} maxBarSize={46} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="stats-nodata">Недостаточно данных</p>
            )}
          </SectionCard>

          {/* Частота */}
          <SectionCard title="Частота тренировок" hint={scope === "plan" ? "по микроциклам" : "по неделям"} testid="stats-frequency-chart">
            {frequency.length ? (
              <div className="stats-chart stats-chart-sm">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={frequency} margin={{ top: 8, right: 4, left: -22, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="week" tickFormatter={shortWeek} tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} axisLine={false} tickLine={false} width={28} />
                    <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} content={<ChartTooltip unit="трен." />} />
                    <Bar dataKey="count" name="Тренировок" fill="#36C5F0" radius={[6, 6, 0, 0]} maxBarSize={38} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="stats-nodata">Недостаточно данных</p>
            )}
          </SectionCard>

          {/* Прогресс упражнения */}
          <SectionCard
            title="Прогресс упражнения"
            hint="рабочий вес: факт / план"
            testid="stats-exercise-progress"
            action={
              exercises.length ? (
                <div className="stats-select-wrap">
                  <select
                    className="stats-select"
                    value={selectedSlug || ""}
                    onChange={(e) => setSelectedSlug(e.target.value)}
                    data-testid="exercise-select"
                  >
                    {exercises.map((ex) => (
                      <option key={ex.key} value={ex.key}>{ex.name}</option>
                    ))}
                  </select>
                  <ChevronDown size={16} className="stats-select-ic" />
                </div>
              ) : null
            }
          >
            {series.length ? (
              <div className="stats-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={series} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.06)" />
                    <XAxis dataKey="label" tick={{ fill: "rgba(255,255,255,0.5)", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "rgba(255,255,255,0.45)", fontSize: 11 }} axisLine={false} tickLine={false} width={40} domain={["auto", "auto"]} />
                    <Tooltip content={<ChartTooltip unit="кг" />} />
                    <Line type="monotone" dataKey="plan_weight" name="План" stroke="rgba(255,255,255,0.35)" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                    <Line type="monotone" dataKey="top_weight" name="Факт" stroke="#FF8A24" strokeWidth={3} dot={{ r: 3, fill: "#FF8A24" }} activeDot={{ r: 5 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="stats-nodata">Нет выполненных подходов по упражнению</p>
            )}
          </SectionCard>

          {/* Группы мышц */}
          {muscles.length ? (
            <SectionCard title="Распределение по группам" hint="подходы" testid="stats-muscles">
              <div className="stats-pie-wrap">
                <div className="stats-pie">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={muscles}
                        dataKey="sets"
                        nameKey="label"
                        cx="50%"
                        cy="50%"
                        innerRadius="58%"
                        outerRadius="92%"
                        paddingAngle={2}
                        stroke="none"
                      >
                        {muscles.map((m, i) => (
                          <Cell key={m.group} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip content={<ChartTooltip unit="подх." />} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="stats-pie-center">
                    <b>{totalMuscleSets}</b>
                    <span>подходов</span>
                  </div>
                </div>
                <ul className="stats-legend">
                  {muscles.map((m, i) => (
                    <li key={m.group} data-testid={`muscle-${m.group}`}>
                      <span className="stats-legend-dot" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      <span className="stats-legend-name">{m.label}</span>
                      <b className="stats-legend-val">{m.sets}</b>
                    </li>
                  ))}
                </ul>
              </div>
            </SectionCard>
          ) : null}

          {/* Adherence — соответствие плану */}
          <SectionCard title="Соответствие плану" hint="план ↔ факт" testid="stats-adherence">
            <div className="stats-bars">
              <AdherenceBar label="Объём (подходы)" value={adherence.volume_pct} />
              {adherence.schedule_pct != null ? (
                <AdherenceBar label="Расписание" value={adherence.schedule_pct} />
              ) : null}
              <DeviationRow label="Отклонение по тоннажу" value={adherence.tonnage_dev_pct} />
            </div>
            {Object.keys(skipCounts).length ? (
              <div className="stats-chips" data-testid="stats-skip-chips">
                {Object.entries(SKIP_META).map(([k, meta]) => {
                  const n = skipCounts[k] || 0;
                  if (!n) return null;
                  const Ic = meta.Icon;
                  return (
                    <span className="stats-chip" key={k} style={{ color: meta.color, borderColor: `${meta.color}55`, background: `${meta.color}18` }}>
                      <Ic size={13} /> {meta.label} <b>{n}</b>
                    </span>
                  );
                })}
              </div>
            ) : null}
          </SectionCard>

          {/* Последние тренировки */}
          {recent.length ? (
            <SectionCard title="Последние тренировки" testid="stats-recent">
              <ul className="stats-recent">
                {recent.map((s) => (
                  <li className="stats-recent-row" key={s.id} data-testid={`recent-${s.id}`}>
                    <div className="stats-recent-ring" style={{ "--p": `${s.progress_pct || 0}%` }}>
                      <span>{s.progress_pct || 0}<i>%</i></span>
                    </div>
                    <div className="stats-recent-main">
                      <div className="stats-recent-title">
                        {s.title || "Тренировка"}
                        {s.coach_confirmed ? <ShieldCheck size={13} className="stats-recent-ok" /> : null}
                      </div>
                      <div className="stats-recent-meta">
                        {s.group ? <span className="stats-recent-group">{s.group}</span> : null}
                        <span>{fmtTon(s.tonnage)}</span>
                        <span>·</span>
                        <span>{fmtDur(s.duration_sec)}</span>
                        {s.difficulty ? <><span>·</span><span>{s.difficulty}</span></> : null}
                      </div>
                    </div>
                    <div className="stats-recent-date">{formatShortDate(s.date || s.finished_at)}</div>
                  </li>
                ))}
              </ul>
            </SectionCard>
          ) : null}

          <div className="stats-foot-space" />
        </>
      )}
    </div>
  );
}

function AdherenceBar({ label, value }) {
  const v = Math.max(0, Math.min(100, Math.round(value || 0)));
  const color = v >= 85 ? "#34D399" : v >= 60 ? "#FFC24B" : "#FB7185";
  return (
    <div className="stats-bar">
      <div className="stats-bar-top">
        <span>{label}</span>
        <b style={{ color }}>{v}%</b>
      </div>
      <div className="stats-bar-track">
        <div className="stats-bar-fill" style={{ width: `${v}%`, background: color }} />
      </div>
    </div>
  );
}

function DeviationRow({ label, value }) {
  const v = Math.round(value || 0);
  const pos = v >= 0;
  return (
    <div className="stats-dev">
      <span>{label}</span>
      <b className={pos ? "up" : "down"}>{pos ? "+" : ""}{v}%</b>
    </div>
  );
}

function formatShortDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
  } catch (e) {
    return "";
  }
}

export function StatsPage() {
  const { user, avatarUrl } = useUser();
  const navigate = useNavigate();
  const tg = user?.telegram_id;
  useBackButton(true, () => navigate(-1));

  const fetchPlanId = useCallback(() => getActivePlan(tg).then((p) => p?.id), [tg]);
  const fetchDetailed = useCallback((params) => getDetailedStats(tg, params), [tg]);
  const fetchProgress = useCallback((params) => getExerciseProgress(tg, params), [tg]);

  if (!tg) return null;
  return (
    <StatsView
      name={user?.first_name || "Моя статистика"}
      avatar={avatarUrl}
      subtitle="Моя статистика"
      onBack={() => navigate(-1)}
      fetchPlanId={fetchPlanId}
      fetchDetailed={fetchDetailed}
      fetchProgress={fetchProgress}
    />
  );
}

export function CoachClientStatsPage() {
  const { athleteId } = useParams();
  const aid = Number(athleteId);
  const { user } = useUser();
  const coachId = user?.telegram_id;
  const navigate = useNavigate();
  const [athlete, setAthlete] = useState(null);
  useBackButton(true, () => navigate(`/coach/${aid}`));

  useEffect(() => {
    let alive = true;
    getUserById(aid).then((u) => alive && setAthlete(u)).catch(() => {});
    return () => { alive = false; };
  }, [aid]);

  const fetchPlanId = useCallback(
    () => getCoachClientPlan(coachId, aid).then((p) => p?.id),
    [coachId, aid]
  );
  const fetchDetailed = useCallback(
    (params) => getCoachClientStats(coachId, aid, params),
    [coachId, aid]
  );
  const fetchProgress = useCallback(
    (params) => getCoachClientExerciseProgress(coachId, aid, params),
    [coachId, aid]
  );

  if (!coachId || !aid) return null;
  return (
    <StatsView
      name={athlete?.first_name || "Подопечный"}
      avatar={athlete?.picture}
      subtitle="Статистика подопечного"
      onBack={() => navigate(`/coach/${aid}`)}
      fetchPlanId={fetchPlanId}
      fetchDetailed={fetchDetailed}
      fetchProgress={fetchProgress}
    />
  );
}

export default StatsPage;
