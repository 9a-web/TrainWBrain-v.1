import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import {
  createDiarySession,
  diaryParse,
  pollDiaryJob,
  getExercises,
} from "@/api";
import "@/components/Diary.css";

const emptyGroup = () => ({ weight: "", sets: "3", reps: "10" });
const emptyRow = () => ({ name: "", is_accessory: false, groups: [emptyGroup()] });

// sets_scheme (массив групп) -> строки редактора
const schemeToGroups = (scheme) => {
  const g = (scheme || []).map((s) => ({
    weight: s.weight != null ? String(s.weight) : "",
    sets: String(s.sets || 3),
    reps: String(s.reps || 10),
  }));
  return g.length ? g : [emptyGroup()];
};

const exToRow = (e) => ({
  name: e.name || "",
  is_accessory: !!e.is_accessory,
  groups: schemeToGroups(e.sets_scheme),
});

// Композер: запись выполненной тренировки. Способы — Быстро и Текст (ИИ).
const DiaryComposer = ({ open, onClose, date, onSaved, prefill }) => {
  const [tab, setTab] = useState("quick");
  const [rows, setRows] = useState([emptyRow()]);
  const [rpe, setRpe] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyMsg, setBusyMsg] = useState("");
  const [catalog, setCatalog] = useState([]);

  useEffect(() => {
    if (!open) return;
    getExercises().then((list) => setCatalog(list || [])).catch(() => {});
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (prefill && prefill.length) {
      setRows(prefill.map(exToRow));
      setTab("quick");
    } else {
      setRows([emptyRow()]);
      setText("");
      setRpe(null);
      setTab("quick");
    }
  }, [open, prefill]);

  if (!open) return null;

  const updateRow = (i, patch) =>
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  const addRow = () => setRows((rs) => [...rs, emptyRow()]);
  const removeRow = (i) => setRows((rs) => (rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs));

  const updateGroup = (i, gi, patch) =>
    setRows((rs) =>
      rs.map((r, idx) =>
        idx === i
          ? { ...r, groups: r.groups.map((g, gidx) => (gidx === gi ? { ...g, ...patch } : g)) }
          : r
      )
    );
  const addGroup = (i) =>
    setRows((rs) =>
      rs.map((r, idx) => {
        if (idx !== i) return r;
        const last = r.groups[r.groups.length - 1] || emptyGroup();
        // новый подход берёт повторы/подходы последней группы как подсказку
        return { ...r, groups: [...r.groups, { weight: "", sets: "1", reps: last.reps }] };
      })
    );
  const removeGroup = (i, gi) =>
    setRows((rs) =>
      rs.map((r, idx) =>
        idx === i && r.groups.length > 1
          ? { ...r, groups: r.groups.filter((_, gidx) => gidx !== gi) }
          : r
      )
    );

  const rowsToExercises = () =>
    rows
      .filter((r) => (r.name || "").trim())
      .map((r) => {
        const sets_scheme = r.is_accessory
          ? []
          : r.groups
              .map((g) => ({
                weight: g.weight === "" ? null : parseFloat(g.weight),
                sets: parseInt(g.sets, 10) || 1,
                reps: parseInt(g.reps, 10) || 0,
              }))
              .filter((g) => g.reps > 0 || g.weight != null);
        return { name: r.name.trim(), is_accessory: r.is_accessory, sets_scheme };
      });

  const handleSave = async (exercises) => {
    const exs = exercises || rowsToExercises();
    if (!exs.length) {
      toast.error("Добавь хотя бы одно упражнение");
      return;
    }
    setBusy(true);
    setBusyMsg("Сохраняю...");
    try {
      const session = await createDiarySession({
        date,
        rpe: rpe || null,
        source_input: tab === "text" ? "text" : "quick",
        exercises: exs,
      });
      toast.success("Тренировка записана");
      window.dispatchEvent(new Event("twb:progress"));
      onSaved && onSaved(session);
      onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Не удалось сохранить");
    } finally {
      setBusy(false);
      setBusyMsg("");
    }
  };

  const handleParse = async () => {
    if ((text || "").trim().length < 3) {
      toast.error("Опиши тренировку подробнее");
      return;
    }
    setBusy(true);
    setBusyMsg("ИИ распознаёт запись...");
    try {
      const { job_id } = await diaryParse(text.trim());
      const job = await pollDiaryJob(job_id);
      if (job.status !== "done" || !job.template) {
        throw new Error(job.error || "Не удалось распознать");
      }
      setRows((job.template.exercises || []).map(exToRow));
      setTab("quick");
      toast.success("Распознано — проверь и сохрани");
    } catch (e) {
      toast.error(e?.response?.data?.detail || e.message || "Ошибка распознавания");
    } finally {
      setBusy(false);
      setBusyMsg("");
    }
  };

  return (
    <div className="diary-modal-backdrop" onClick={onClose} data-testid="diary-composer">
      <div className="diary-modal" onClick={(e) => e.stopPropagation()}>
        <div className="diary-modal-head">
          <h3>Записать тренировку</h3>
          <button className="diary-modal-close" onClick={onClose} data-testid="diary-composer-close">
            ×
          </button>
        </div>

        <div className="diary-tabs">
          <button
            className={tab === "quick" ? "active" : ""}
            onClick={() => setTab("quick")}
            data-testid="diary-tab-quick"
          >
            Быстро
          </button>
          <button
            className={tab === "text" ? "active" : ""}
            onClick={() => setTab("text")}
            data-testid="diary-tab-text"
          >
            Текст (ИИ)
          </button>
        </div>

        {tab === "text" && (
          <div>
            <textarea
              className="diary-textarea"
              placeholder={"Опиши, что сделал. Например:\nприсед 100х5х3 потом 110х3, жим лёжа 80 8 8 8, подтягивания 3 подхода по 10"}
              value={text}
              onChange={(e) => setText(e.target.value)}
              data-testid="diary-composer-text"
            />
            <p className="diary-hint-txt">
              ИИ распознает упражнения и подходы (в т.ч. разные веса). Дальше проверишь и сохранишь.
            </p>
            <button
              className="diary-btn diary-btn-primary"
              onClick={handleParse}
              disabled={busy}
              data-testid="diary-parse-btn"
            >
              {busy ? <span className="diary-spinner" /> : "Распознать"}
            </button>
          </div>
        )}

        {tab === "quick" && (
          <div>
            {rows.map((r, i) => (
              <div className="qx-row" key={i}>
                <div className="qx-row-head">
                  <input
                    className="qx-name"
                    list="diary-ex-catalog"
                    placeholder="Упражнение"
                    value={r.name}
                    onChange={(e) => updateRow(i, { name: e.target.value })}
                    data-testid={`diary-ex-name-${i}`}
                  />
                  {rows.length > 1 && (
                    <button
                      className="qx-row-remove"
                      onClick={() => removeRow(i)}
                      aria-label="Удалить упражнение"
                    >
                      <X size={18} />
                    </button>
                  )}
                </div>

                {!r.is_accessory && (
                  <>
                    {r.groups.map((g, gi) => (
                      <div className="qx-group" key={gi}>
                        <div className="qx-nums">
                          <div className="qx-num">
                            {gi === 0 && <label>Вес, кг</label>}
                            <input
                              type="number"
                              inputMode="decimal"
                              value={g.weight}
                              onChange={(e) => updateGroup(i, gi, { weight: e.target.value })}
                              placeholder="—"
                              data-testid={`diary-ex-weight-${i}-${gi}`}
                            />
                          </div>
                          <div className="qx-num">
                            {gi === 0 && <label>Подходы</label>}
                            <input
                              type="number"
                              inputMode="numeric"
                              value={g.sets}
                              onChange={(e) => updateGroup(i, gi, { sets: e.target.value })}
                              data-testid={`diary-ex-sets-${i}-${gi}`}
                            />
                          </div>
                          <div className="qx-num">
                            {gi === 0 && <label>Повторы</label>}
                            <input
                              type="number"
                              inputMode="numeric"
                              value={g.reps}
                              onChange={(e) => updateGroup(i, gi, { reps: e.target.value })}
                              data-testid={`diary-ex-reps-${i}-${gi}`}
                            />
                          </div>
                          {r.groups.length > 1 && (
                            <button
                              className="qx-group-remove"
                              onClick={() => removeGroup(i, gi)}
                              aria-label="Убрать подход"
                            >
                              <X size={16} />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                    <button
                      className="qx-add-group"
                      onClick={() => addGroup(i)}
                      data-testid={`diary-add-group-${i}`}
                    >
                      <Plus size={14} /> подход с другим весом
                    </button>
                  </>
                )}

                <label className="qx-acc">
                  <input
                    type="checkbox"
                    checked={r.is_accessory}
                    onChange={(e) => updateRow(i, { is_accessory: e.target.checked })}
                  />
                  Подсобное (без веса)
                </label>
              </div>
            ))}
            <datalist id="diary-ex-catalog">
              {catalog.map((ex) => (
                <option key={ex.id} value={ex.name} />
              ))}
            </datalist>

            <button className="diary-btn-sm" onClick={addRow} data-testid="diary-add-ex">
              + Добавить упражнение
            </button>

            <div className="ob-label" style={{ marginTop: 16 }}>
              Насколько тяжело было? (RPE, необязательно)
            </div>
            <div className="rpe-row">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <button
                  key={n}
                  className={rpe === n ? "sel" : ""}
                  onClick={() => setRpe(rpe === n ? null : n)}
                  data-testid={`diary-rpe-${n}`}
                >
                  {n}
                </button>
              ))}
            </div>

            {busyMsg && <div className="busy-note">{busyMsg}</div>}
            <button
              className="diary-btn diary-btn-primary"
              onClick={() => handleSave()}
              disabled={busy}
              data-testid="diary-save-btn"
            >
              {busy ? <span className="diary-spinner" /> : "Сохранить тренировку"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default DiaryComposer;
