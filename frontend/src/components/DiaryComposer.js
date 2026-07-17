import React, { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  createDiarySession,
  diaryParse,
  pollDiaryJob,
  getExercises,
} from "@/api";
import "@/components/Diary.css";

const emptyRow = () => ({ name: "", weight: "", sets: "3", reps: "10", is_accessory: false });

// Композер: запись выполненной тренировки. Два способа — Быстро и Текст (ИИ).
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
      setRows(
        prefill.map((e) => {
          const s = (e.sets_scheme && e.sets_scheme[0]) || {};
          return {
            name: e.name || "",
            weight: s.weight != null ? String(s.weight) : "",
            sets: String(s.sets || 3),
            reps: String(s.reps || 10),
            is_accessory: !!e.is_accessory,
          };
        })
      );
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

  const rowsToExercises = () =>
    rows
      .filter((r) => (r.name || "").trim())
      .map((r) => {
        const sets = parseInt(r.sets, 10) || 1;
        const reps = parseInt(r.reps, 10) || 0;
        const weight = r.weight === "" ? null : parseFloat(r.weight);
        return {
          name: r.name.trim(),
          is_accessory: r.is_accessory,
          sets_scheme: r.is_accessory ? [] : [{ weight, sets, reps }],
        };
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
      const exs = job.template.exercises || [];
      // Перенесём в быстрый редактор для подтверждения/правки
      setRows(
        exs.map((e) => {
          const s = (e.sets_scheme && e.sets_scheme[0]) || {};
          return {
            name: e.name || "",
            weight: s.weight != null ? String(s.weight) : "",
            sets: String(s.sets || 3),
            reps: String(s.reps || 10),
            is_accessory: !!e.is_accessory,
          };
        })
      );
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
              placeholder={"Опиши, что сделал. Например:\nприсед 100х5х3, жим лёжа 80 8 8 8, подтягивания 3 подхода по 10"}
              value={text}
              onChange={(e) => setText(e.target.value)}
              data-testid="diary-composer-text"
            />
            <p className="diary-hint-txt">
              ИИ распознает упражнения и подходы. Дальше проверишь и сохранишь.
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
                <input
                  className="qx-name"
                  list="diary-ex-catalog"
                  placeholder="Упражнение"
                  value={r.name}
                  onChange={(e) => updateRow(i, { name: e.target.value })}
                  data-testid={`diary-ex-name-${i}`}
                />
                {!r.is_accessory && (
                  <div className="qx-nums">
                    <div className="qx-num">
                      <label>Вес, кг</label>
                      <input
                        type="number"
                        inputMode="decimal"
                        value={r.weight}
                        onChange={(e) => updateRow(i, { weight: e.target.value })}
                        placeholder="—"
                        data-testid={`diary-ex-weight-${i}`}
                      />
                    </div>
                    <div className="qx-num">
                      <label>Подходы</label>
                      <input
                        type="number"
                        inputMode="numeric"
                        value={r.sets}
                        onChange={(e) => updateRow(i, { sets: e.target.value })}
                        data-testid={`diary-ex-sets-${i}`}
                      />
                    </div>
                    <div className="qx-num">
                      <label>Повторы</label>
                      <input
                        type="number"
                        inputMode="numeric"
                        value={r.reps}
                        onChange={(e) => updateRow(i, { reps: e.target.value })}
                        data-testid={`diary-ex-reps-${i}`}
                      />
                    </div>
                  </div>
                )}
                <label className="qx-acc">
                  <input
                    type="checkbox"
                    checked={r.is_accessory}
                    onChange={(e) => updateRow(i, { is_accessory: e.target.checked })}
                  />
                  Подсобное (без веса)
                </label>
                {rows.length > 1 && (
                  <button className="qx-remove" onClick={() => removeRow(i)}>
                    Удалить
                  </button>
                )}
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
