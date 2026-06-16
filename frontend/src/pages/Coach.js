import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Copy, Link2, Users, Activity, ChevronRight, Dumbbell } from "lucide-react";
import { toast } from "sonner";
import { useUser } from "@/context/UserContext";
import { getCoachClients, coachInvite } from "@/api";
import { haptic } from "@/lib/platform";
import { useBackButton } from "@/hooks/useTelegramUI";
import "./Coach.css";

const fmtDate = (iso) => {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  } catch (e) {
    return null;
  }
};

const avatarFor = (c) => {
  const a = c.athlete || {};
  if (a.picture) return a.picture;
  const name = encodeURIComponent(a.first_name || "U");
  return `https://ui-avatars.com/api/?name=${name}&background=FF6B00&color=fff&size=80&bold=true`;
};

export default function Coach() {
  const { user } = useUser();
  const navigate = useNavigate();
  useBackButton(true, () => navigate("/"));
  const coachId = user?.telegram_id;

  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [invite, setInvite] = useState(null);

  const load = useCallback(async () => {
    if (!coachId) return;
    setLoading(true);
    try {
      const [inv, data] = await Promise.all([
        coachInvite(coachId).catch(() => null),
        getCoachClients(coachId),
      ]);
      setInvite(inv);
      setClients(data.clients || []);
    } catch (e) {
      toast.error("Не удалось загрузить подопечных");
    } finally {
      setLoading(false);
    }
  }, [coachId]);

  useEffect(() => {
    load();
  }, [load]);

  const copy = async (text, label) => {
    if (!text) return;
    haptic("light");
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${label} скопирован${label === "Ссылка" ? "а" : ""}`);
    } catch (e) {
      toast.info(text);
    }
  };

  return (
    <div className="coach-page" data-testid="coach-page">
      <header className="coach-header">
        <button className="coach-back" onClick={() => navigate("/")} aria-label="Назад" data-testid="coach-back">
          <ArrowLeft size={22} />
        </button>
        <h1 className="coach-title">Кабинет тренера</h1>
      </header>

      {/* Приглашение */}
      <div className="coach-invite-card" data-testid="coach-invite-card">
        <div className="coach-invite-top">
          <Users size={18} />
          <span>Пригласить спортсмена</span>
        </div>
        <p className="coach-invite-hint">
          Дайте этот код спортсмену — он введёт его в своём профиле и привяжется к вам.
        </p>
        <div className="coach-invite-code" data-testid="coach-invite-code">
          {invite?.invite_code || "········"}
        </div>
        <div className="coach-invite-actions">
          <button className="coach-chip-btn" onClick={() => copy(invite?.invite_code, "Код")} data-testid="copy-code-btn">
            <Copy size={15} /> Код
          </button>
          {invite?.deep_link ? (
            <button className="coach-chip-btn" onClick={() => copy(invite?.deep_link, "Ссылка")} data-testid="copy-link-btn">
              <Link2 size={15} /> Ссылка
            </button>
          ) : null}
        </div>
      </div>

      <h2 className="coach-section-title">Подопечные{clients.length ? ` · ${clients.length}` : ""}</h2>

      {loading ? (
        <div className="coach-empty">Загрузка…</div>
      ) : clients.length === 0 ? (
        <div className="coach-empty" data-testid="coach-empty">
          Пока нет подопечных. Поделитесь кодом приглашения выше.
        </div>
      ) : (
        <div className="coach-clients">
          {clients.map((c) => {
            const a = c.athlete || {};
            const last = fmtDate(c.last_workout_at);
            return (
              <button
                key={a.telegram_id}
                className="client-card"
                onClick={() => {
                  haptic("light");
                  navigate(`/coach/${a.telegram_id}`);
                }}
                data-testid={`client-card-${a.telegram_id}`}
              >
                <img className="client-avatar" src={avatarFor(c)} alt="" />
                <div className="client-main">
                  <div className="client-name-row">
                    <span className="client-name">{a.first_name || "Спортсмен"}</span>
                    {c.is_training_now ? (
                      <span className="client-live" data-testid="client-live">
                        <Activity size={12} /> тренируется
                      </span>
                    ) : null}
                  </div>
                  <div className="client-sub">
                    {c.plan ? (
                      <>
                        <Dumbbell size={13} />
                        <span className="client-plan-name">{c.plan.name}</span>
                        <span className={`vis-badge vis-${c.plan.visibility}`}>
                          {c.plan.visibility === "draft" ? "черновик" : "опубликован"}
                        </span>
                      </>
                    ) : (
                      <span className="client-noplan">Нет программы</span>
                    )}
                  </div>
                  <div className="client-meta">
                    {last ? `Последняя тренировка: ${last}` : "Тренировок ещё не было"}
                  </div>
                </div>
                <ChevronRight size={20} className="client-chevron" />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
