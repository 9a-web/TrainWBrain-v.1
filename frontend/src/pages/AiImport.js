import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft, Sparkles, FileText, Wand2, Upload, KeyRound,
  CheckCircle2, PencilLine, Dumbbell,
} from "lucide-react";
import { toast } from "sonner";
import {
  getAiStatus, aiGenerateProgram, aiParseProgram, aiParseProgramFile,
} from "@/api";
import { hapticNotify } from "@/lib/platform";
import { useBackButton } from "@/hooks/useTelegramUI";
import "./AiImport.css";

const EXAMPLES = [
  "3 тренировки в неделю на силу, база: присед, жим, тяга",
  "Программа на массу 4 дня в неделю, верх/низ",
  "Подготовка к соревнованиям по пауэрлифтингу, 8 недель",
];
const BUSY_STEPS = [
  "Анализируем запрос…",
  "Подбираем упражнения…",
  "Строим недели и дни…",
  "Расставляем веса и подходы…",
  "Почти готово…",
];

const errText = (e, fallback) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
};

function BusyOverlay() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => (s + 1) % BUSY_STEPS.length), 2600);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="ai-busy" data-testid="ai-busy">
      <span className="ai-busy-orb"><Sparkles size={26} /></span>
      <p>{BUSY_STEPS[step]}</p>
      <span className="ai-busy-sub">Обычно занимает 20–60 секунд</span>
    </div>
  );
}

export default function AiImport() {
  const navigate = useNavigate();
  useBackButton(true, () => navigate("/programs"));

  const [status, setStatus] = useState(null);
  const [tab, setTab] = useState("generate"); // generate | parse
  const [prompt, setPrompt] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    getAiStatus().then(setStatus).catch(() => setStatus({ enabled: false }));
  }, []);

  const enabled = !!status?.enabled;

  const run = async (fn) => {
    setBusy(true);
    setResult(null);
    try {
      const tpl = await fn();
      setResult(tpl);
      hapticNotify("success");
      toast.success(`Программа «${tpl.name}» сохранена в «Мои программы»`);
    } catch (e) {
      hapticNotify("error");
      toast.error(errText(e, "Не удалось обработать запрос"));
    } finally {
      setBusy(false);
    }
  };

  const generate = () => {
    if (prompt.trim().length < 10) {
      toast.error("Опишите пожелания подробнее");
      return;
    }
    run(() => aiGenerateProgram(prompt.trim()));
  };

  const parse = () => {
    if (file) {
      run(() => aiParseProgramFile(file));
      return;
    }
    if (text.trim().length < 20) {
      toast.error("Вставьте текст плана или выберите файл");
      return;
    }
    run(() => aiParseProgram(text.trim()));
  };

  const totalEx = result
    ? (result.weeks || []).reduce(
        (a, w) => a + (w.days || []).reduce((b, d) => b + (d.exercises || []).length, 0), 0)
    : 0;

  return (
    <div className="ai-page" data-testid="ai-page">
      <div className="ai-ambient" aria-hidden="true" />
      <header className="ai-header">
        <button className="ai-back" onClick={() => navigate("/programs")}
          aria-label="Назад" data-testid="ai-back">
          <ArrowLeft size={22} />
        </button>
        <div>
          <h1 className="ai-title">ИИ-анализ</h1>
          <span className="ai-model">{status?.model || "deepseek-v4-flash"}</span>
        </div>
      </header>

      {status && !enabled ? (
        <div className="ai-disabled" data-testid="ai-disabled">
          <KeyRound size={18} />
          <div>
            <b>ИИ пока не подключён</b>
            <p>Функция станет активной после добавления API-ключа сервиса (DeepSeek / openmodel / routerai).</p>
          </div>
        </div>
      ) : null}

      <div className="ai-tabs">
        <button className={`ai-tab ${tab === "generate" ? "active" : ""}`}
          onClick={() => setTab("generate")} data-testid="ai-tab-generate">
          <Wand2 size={15} /> По описанию
        </button>
        <button className={`ai-tab ${tab === "parse" ? "active" : ""}`}
          onClick={() => setTab("parse")} data-testid="ai-tab-parse">
          <FileText size={15} /> Готовый план
        </button>
      </div>

      {busy ? (
        <BusyOverlay />
      ) : result ? (
        <div className="ai-result" data-testid="ai-result">
          <span className="ai-result-ok"><CheckCircle2 size={24} /></span>
          <h3 className="ai-result-name">{result.name}</h3>
          {result.description ? <p className="ai-result-desc">{result.description}</p> : null}
          <div className="ai-result-meta">
            <span>{result.weeks_count} нед.</span>
            <span>·</span>
            <span>{result.days_per_week || "—"} дн./нед.</span>
            <span>·</span>
            <span>{totalEx} упражнений</span>
            {result.requires_maxes ? (<><span>·</span><span className="ai-pct">%1ПМ</span></>) : null}
          </div>
          <div className="ai-result-actions">
            <button className="ai-btn-secondary"
              onClick={() => navigate(`/programs/builder/${result.id}`)} data-testid="ai-open-builder">
              <PencilLine size={15} /> В конструкторе
            </button>
            <button className="ai-btn-primary" onClick={() => navigate("/programs")}
              data-testid="ai-to-programs">
              <Dumbbell size={15} /> К программам
            </button>
          </div>
          <button className="ai-again" onClick={() => setResult(null)} data-testid="ai-again">
            Создать ещё одну
          </button>
        </div>
      ) : tab === "generate" ? (
        <div className="ai-panel">
          <p className="ai-hint">Опишите цель, опыт, сколько дней в неделю и что любите делать — ИИ соберёт программу.</p>
          <textarea className="ai-textarea" rows={5} value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Например: хочу программу на силу, 3 дня в неделю, приседаю 120 кг…"
            data-testid="ai-prompt" />
          <div className="ai-examples">
            {EXAMPLES.map((ex) => (
              <button key={ex} className="ai-example" onClick={() => setPrompt(ex)}>{ex}</button>
            ))}
          </div>
          <button className="ai-btn-primary ai-submit" onClick={generate}
            disabled={!enabled || prompt.trim().length < 10} data-testid="ai-generate-btn">
            <Sparkles size={16} /> Сгенерировать программу
          </button>
        </div>
      ) : (
        <div className="ai-panel">
          <p className="ai-hint">Вставьте план текстом (можно прямо из Excel/заметок) или загрузите файл — ИИ разберёт его в структуру.</p>
          <textarea className="ai-textarea" rows={7} value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={"Неделя 1\nПн: Присед 5×5 80%, Жим лёжа 5×5 75%…"}
            data-testid="ai-text" />
          <input ref={fileRef} type="file" accept=".xlsx,.csv,.txt,.tsv,.md"
            style={{ display: "none" }}
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            data-testid="ai-file-input" />
          <button className="ai-file-btn" onClick={() => fileRef.current?.click()} data-testid="ai-file-btn">
            <Upload size={15} />
            {file ? file.name : "Загрузить файл (.xlsx / .csv / .txt)"}
            {file ? (
              <span className="ai-file-clear" onClick={(e) => { e.stopPropagation(); setFile(null); fileRef.current.value = ""; }}>
                ×
              </span>
            ) : null}
          </button>
          <button className="ai-btn-primary ai-submit" onClick={parse}
            disabled={!enabled || (!file && text.trim().length < 20)} data-testid="ai-parse-btn">
            <Sparkles size={16} /> Разобрать план
          </button>
        </div>
      )}
    </div>
  );
}
