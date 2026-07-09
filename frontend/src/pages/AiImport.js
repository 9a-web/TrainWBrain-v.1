import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft, Sparkles, FileText, Wand2, Upload, KeyRound,
  CheckCircle2, PencilLine, Dumbbell, Eye,
} from "lucide-react";
import { toast } from "sonner";
import { GrainGradient, MeshGradient } from "@paper-design/shaders-react";
import {
  getAiStatus, aiGenerateProgram, aiParseProgram, aiParseProgramFile, aiProgramQuestions, getAiJob,
} from "@/api";
import { hapticNotify } from "@/lib/platform";
import { useBackButton } from "@/hooks/useTelegramUI";
import { AiProgressChart } from "@/components/AiProgressChart";
import { AiProgramPreview } from "@/components/AiProgramPreview";
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
const QUESTIONS_BUSY_STEPS = [
  "Изучаем ваш запрос…",
  "Готовим уточняющие вопросы…",
];

const errText = (e, fallback) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
};

function BusyOverlay({ steps = BUSY_STEPS, sub = "Обычно занимает 30–90 секунд" }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => (s + 1) % steps.length), 2600);
    return () => clearInterval(t);
  }, [steps]);
  return (
    <div className="ai-busy" data-testid="ai-busy">
      <div className="ai-busy-shader" aria-hidden="true">
        <GrainGradient
          width="100%"
          height="100%"
          colors={["#ff8a24", "#ffda24", "#ff5e00", "#7a1a00"]}
          colorBack="#1c1c1c"
          softness={0.85}
          intensity={0.55}
          noise={0.35}
          shape="wave"
          speed={1.1}
        />
      </div>
      <span className="ai-busy-orb"><Sparkles size={26} /></span>
      <p>{steps[step]}</p>
      <span className="ai-busy-sub">{sub}</span>
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
  const [busyKind, setBusyKind] = useState("program"); // program | questions
  const [result, setResult] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [qStep, setQStep] = useState("basic"); // basic | advanced
  const [picked, setPicked] = useState({});
  const [custom, setCustom] = useState({});
  const [showPreview, setShowPreview] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    getAiStatus().then(setStatus).catch(() => setStatus({ enabled: false }));
  }, []);

  const enabled = !!status?.enabled;

  const run = async (fn) => {
    setBusyKind("program");
    setBusy(true);
    setResult(null);
    try {
      const started = await fn();
      let tpl = started;
      if (started?.job_id) {
        let fails = 0;
        const deadline = Date.now() + 5 * 60 * 1000;
        for (;;) {
          if (Date.now() > deadline) {
            throw { response: { data: { detail: "ИИ отвечает слишком долго — попробуйте ещё раз" } } };
          }
          await new Promise((r) => setTimeout(r, 3000));
          let job;
          try {
            job = await getAiJob(started.job_id);
            fails = 0;
          } catch (e) {
            if (++fails >= 3) throw e;
            continue;
          }
          if (job.status === "done") { tpl = job.template; break; }
          if (job.status === "error") {
            throw { response: { data: { detail: job.error } } };
          }
        }
      }
      setResult(tpl);
      setQuestions(null);
      hapticNotify("success");
      toast.success(`Программа «${tpl.name}» сохранена в «Мои программы»`);
    } catch (e) {
      hapticNotify("error");
      toast.error(errText(e, "Не удалось обработать запрос"));
    } finally {
      setBusy(false);
    }
  };

  const askQuestions = async () => {
    if (prompt.trim().length < 10) {
      toast.error("Опишите пожелания подробнее");
      return;
    }
    setBusyKind("questions");
    setBusy(true);
    try {
      const res = await aiProgramQuestions(prompt.trim());
      if (res?.questions?.length) {
        setQuestions(res.questions);
        setQStep("basic");
        setPicked({});
        setCustom({});
        setBusy(false);
      } else {
        await run(() => aiGenerateProgram(prompt.trim()));
      }
    } catch {
      await run(() => aiGenerateProgram(prompt.trim()));
    }
  };

  const collectAnswers = () =>
    (questions || [])
      .map((q, i) => {
        const a = (custom[i] || "").trim() || picked[i] || "";
        return a ? { question: q.question, answer: a } : null;
      })
      .filter(Boolean);

  const generate = (withAnswers) =>
    run(() => aiGenerateProgram(prompt.trim(), withAnswers ? collectAnswers() : []));

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

      {/* Hero — liquid mesh gradient + 3D icon (initial prompt state only) */}
      {!busy && !questions && !result && tab === "generate" ? (
        <div className="ai-hero" data-testid="ai-hero">
          <div className="ai-hero-shader" aria-hidden="true">
            <MeshGradient
              width="100%"
              height="100%"
              colors={["#ff8a24", "#ffda24", "#ff5e00", "#7a1a00", "#1c1c1c"]}
              distortion={0.95}
              swirl={0.65}
              offsetX={0}
              offsetY={0}
              speed={0.55}
              scale={1.2}
              grainMixer={0.28}
              grainOverlay={0.15}
            />
          </div>
          <div className="ai-hero-vignette" aria-hidden="true" />
          <div className="ai-hero-content">
            <img src="/img/3d/star-dot.png" alt="" className="ai-hero-icon" />
            <h2 className="ai-hero-title">
              Программа под вас <span className="ai-hero-accent">за 1 минуту</span>
            </h2>
            <p className="ai-hero-sub">
              Опишите цель — ИИ задаст 8–10 уточняющих вопросов и соберёт программу
              на основе <b>научных исследований</b> и топовых лифтерских методик.
            </p>
            <div className="ai-hero-badges">
              <span className="ai-hero-badge"><b>Wendler</b> 5/3/1</span>
              <span className="ai-hero-badge"><b>Sheiko</b></span>
              <span className="ai-hero-badge"><b>PPL</b> · PHUL · PHAT</span>
              <span className="ai-hero-badge">и ещё 7 схем</span>
            </div>
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
        <BusyOverlay
          steps={busyKind === "questions" ? QUESTIONS_BUSY_STEPS : BUSY_STEPS}
          sub={busyKind === "questions" ? "Обычно занимает 5–15 секунд" : "Обычно занимает 20–60 секунд"}
        />
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
          <AiProgressChart tpl={result} />
          <button className="ai-preview-btn" onClick={() => setShowPreview(true)}
            data-testid="ai-preview-open">
            <Eye size={16} /> Посмотреть программу
          </button>
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
          <button className="ai-again"
            onClick={() => { setResult(null); setQuestions(null); setQStep("basic"); setPicked({}); setCustom({}); }}
            data-testid="ai-again">
            Создать ещё одну
          </button>
          <AiProgramPreview
            open={showPreview}
            tpl={result}
            onClose={() => setShowPreview(false)}
            onUse={() => {
              hapticNotify("success");
              navigate("/programs", { state: { assignTemplateId: result.id } });
            }}
          />
        </div>
      ) : tab === "generate" && questions ? (
        (() => {
          const basicIdx = questions.map((q, i) => (q.tier !== "advanced" ? i : -1)).filter((i) => i >= 0);
          const advIdx = questions.map((q, i) => (q.tier === "advanced" ? i : -1)).filter((i) => i >= 0);
          const hasAdv = advIdx.length > 0;
          const shown = qStep === "basic" || !hasAdv ? basicIdx : advIdx;
          const stepNum = qStep === "basic" ? 1 : 2;
          const totalSteps = hasAdv ? 2 : 1;
          return (
            <div className="ai-panel" data-testid="ai-questions">
              {hasAdv ? (
                <div className="ai-q-stepper" data-testid="ai-q-stepper">
                  <span className={`ai-q-step ${qStep === "basic" ? "active" : "done"}`}>1 · Основное</span>
                  <span className="ai-q-step-sep">→</span>
                  <span className={`ai-q-step ${qStep === "advanced" ? "active" : ""}`}>2 · Тонкая настройка</span>
                </div>
              ) : null}
              <p className="ai-hint">
                {qStep === "basic"
                  ? `Шаг ${stepNum}/${totalSteps}. Ключевые вопросы — от них зависит структура программы.`
                  : `Шаг ${stepNum}/${totalSteps}. Опциональные уточнения. Пропустите — программа всё равно получится хорошей.`}
              </p>
              {shown.map((i) => {
                const q = questions[i];
                return (
                  <div className="ai-q" key={i} data-testid={`ai-question-${i}`}>
                    <p className="ai-q-title">{q.question}</p>
                    {q.options?.length ? (
                      <div className="ai-q-opts">
                        {q.options.map((o) => (
                          <button key={o}
                            className={`ai-chip ${picked[i] === o && !(custom[i] || "").trim() ? "active" : ""}`}
                            onClick={() => {
                              setPicked((p) => ({ ...p, [i]: p[i] === o ? null : o }));
                              setCustom((c) => ({ ...c, [i]: "" }));
                            }}
                            data-testid={`ai-q${i}-opt`}>
                            {o}
                          </button>
                        ))}
                      </div>
                    ) : null}
                    <input className="ai-q-custom" placeholder="Свой ответ…" value={custom[i] || ""}
                      onChange={(e) => setCustom((c) => ({ ...c, [i]: e.target.value }))}
                      data-testid={`ai-q${i}-custom`} />
                  </div>
                );
              })}
              {qStep === "basic" && hasAdv ? (
                <>
                  <button className="ai-btn-primary ai-submit" onClick={() => setQStep("advanced")}
                    data-testid="ai-q-next">
                    Далее — тонкая настройка →
                  </button>
                  <button className="ai-skip" onClick={() => generate(true)} data-testid="ai-generate-basic-only">
                    Сгенерировать без продвинутых
                  </button>
                </>
              ) : (
                <>
                  <button className="ai-btn-primary ai-submit" onClick={() => generate(true)}
                    data-testid="ai-generate-with-answers">
                    <Sparkles size={16} /> Сгенерировать программу
                  </button>
                  <button className="ai-skip" onClick={() => generate(false)} data-testid="ai-generate-skip">
                    Сгенерировать без ответов
                  </button>
                </>
              )}
              <button
                className="ai-again"
                onClick={() => (qStep === "advanced" && hasAdv ? setQStep("basic") : setQuestions(null))}
                data-testid="ai-edit-prompt">
                ← {qStep === "advanced" && hasAdv ? "Назад" : "Изменить запрос"}
              </button>
            </div>
          );
        })()
      ) : tab === "generate" ? (
        <div className="ai-panel">
          <textarea className="ai-textarea" rows={5} value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Например: хочу программу на силу, 3 дня в неделю, приседаю 120 кг…"
            data-testid="ai-prompt" />
          <div className="ai-examples">
            {EXAMPLES.map((ex) => (
              <button key={ex} className="ai-example" onClick={() => setPrompt(ex)}>{ex}</button>
            ))}
          </div>
          <button className="ai-btn-primary ai-submit" onClick={askQuestions}
            disabled={!enabled || prompt.trim().length < 10} data-testid="ai-generate-btn">
            <Sparkles size={16} /> Продолжить
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
