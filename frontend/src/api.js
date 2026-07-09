import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// WebSocket-база (http(s) -> ws(s)), тот же хост/префикс, что и REST (через ingress).
export const WS_BASE = `${BACKEND_URL.replace(/^http/, "ws")}/api/ws`;

// Bearer-token auth (works across web, Telegram WebView and PWA). We deliberately
// do NOT use withCredentials so that CORS "*" stays valid (cannot combine "*"
// with credentials). The session cookie set by the backend is an unused bonus.
const client = axios.create({ baseURL: API });

// --- Auth token (Bearer) ---
const TOKEN_KEY = "twb_token";
export function getAuthToken() {
  try {
    return (typeof window !== "undefined" && window.localStorage.getItem(TOKEN_KEY)) || null;
  } catch (e) {
    return null;
  }
}
export function setAuthToken(token) {
  if (token) {
    client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete client.defaults.headers.common["Authorization"];
  }
}
// Restore token on module load so a page refresh keeps the session
try {
  const saved =
    typeof window !== "undefined" && window.localStorage.getItem(TOKEN_KEY);
  if (saved) setAuthToken(saved);
} catch (e) {
  /* no-op */
}

// --- Аутентификация ---
export const authMe = () => client.get(`/auth/me`).then((r) => r.data);
export const authRegisterEmail = (email, password, name) =>
  client.post(`/auth/register`, { email, password, name }).then((r) => r.data);
export const authLoginEmail = (email, password) =>
  client.post(`/auth/login`, { email, password }).then((r) => r.data);
export const authTelegram = (init_data) =>
  client.post(`/auth/telegram`, { init_data }).then((r) => r.data);
export const authGoogleSession = (session_id) =>
  client.post(`/auth/google/session`, { session_id }).then((r) => r.data);
export const getGoogleConfig = () =>
  client.get(`/auth/google/config`).then((r) => r.data);
export const authGoogleOAuth = (code, redirect_uri) =>
  client.post(`/auth/google/oauth`, { code, redirect_uri }).then((r) => r.data);
export const authLogout = () => client.post(`/auth/logout`).then((r) => r.data);

// --- Пользователи ---
export const registerUser = (payload) =>
  client.post(`/users`, payload).then((r) => r.data);

// --- Упражнения ---
export const getExercises = (params) =>
  client.get(`/exercises`, { params }).then((r) => r.data);
export const createExercise = (payload) =>
  client.post(`/exercises`, payload).then((r) => r.data);

// --- Шаблоны программ ---
export const getTemplates = (params) =>
  client.get(`/programs/templates`, { params }).then((r) => r.data);
export const getTemplate = (id) =>
  client.get(`/programs/templates/${id}`).then((r) => r.data);
export const createTemplate = (payload) =>
  client.post(`/programs/templates`, payload).then((r) => r.data);
export const updateTemplate = (id, body) =>
  client.patch(`/programs/templates/${id}`, body).then((r) => r.data);
export const deleteTemplate = (id) =>
  client.delete(`/programs/templates/${id}`).then((r) => r.data);

// --- P6: шаринг и импорт программ ---
export const shareTemplate = (id) =>
  client.post(`/programs/templates/${id}/share`).then((r) => r.data);
export const getSharedProgram = (code) =>
  client.get(`/programs/shared/${encodeURIComponent(code)}`).then((r) => r.data);
export const importSharedProgram = (code) =>
  client.post(`/programs/import/${encodeURIComponent(code)}`).then((r) => r.data);

// --- P6: ИИ-анализ программ ---
export const getAiStatus = () => client.get(`/ai/status`).then((r) => r.data);
export const aiProgramQuestions = (prompt) =>
  client.post(`/ai/program/questions`, { prompt }).then((r) => r.data);
export const getAiJob = (jobId) =>
  client.get(`/ai/program/jobs/${jobId}`).then((r) => r.data);
export const aiGenerateProgram = (prompt, answers = []) =>
  client.post(`/ai/program/generate`, { prompt, answers }).then((r) => r.data);
export const aiParseProgram = (text) =>
  client.post(`/ai/program/parse`, { text }).then((r) => r.data);
export const aiRefineProgram = (templateId, feedback) =>
  client.post(`/ai/program/refine`, { template_id: templateId, feedback }).then((r) => r.data);
export const aiParseProgramFile = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return client
    .post(`/ai/program/parse-file`, fd, { headers: { "Content-Type": "multipart/form-data" } })
    .then((r) => r.data);
};
export const aiParseProgramPhotos = (files) => {
  const fd = new FormData();
  (files || []).forEach((f) => fd.append("files", f));
  return client
    .post(`/ai/program/parse-photo`, fd, { headers: { "Content-Type": "multipart/form-data" } })
    .then((r) => r.data);
};

// --- Планы ---
export const createPlan = (payload) =>
  client.post(`/plans`, payload).then((r) => r.data);
export const getActivePlan = (telegramId) =>
  client.get(`/plans/active/${telegramId}`).then((r) => r.data);
export const getPlan = (id) =>
  client.get(`/plans/${id}`).then((r) => r.data);
export const cancelPlan = (id) =>
  client.post(`/plans/${id}/cancel`).then((r) => r.data);
export const getPlanDay = (id, week, day, viewer) =>
  client.get(`/plans/${id}/day`, { params: { week, day, ...(viewer != null ? { viewer } : {}) } }).then((r) => r.data);
export const getWeekProgress = (id, week, viewer, dates) =>
  client.get(`/plans/${id}/week-progress`, { params: { week, ...(viewer != null ? { viewer } : {}), ...(dates ? { dates } : {}) } }).then((r) => r.data);

// --- Тренировочные сессии (Phase 2) ---
export const startSession = (payload) =>
  client.post(`/sessions/start`, payload).then((r) => r.data);
export const getSession = (id) =>
  client.get(`/sessions/${id}`).then((r) => r.data);
export const getActiveSession = (params) =>
  client.get(`/sessions/active`, { params }).then((r) => r.data);
export const sessionExerciseAction = (id, order, action, actor, by) =>
  client
    .patch(`/sessions/${id}/exercise/${order}`, null, {
      params: { action, ...(actor ? { actor } : {}), ...(by != null ? { by } : {}) },
    })
    .then((r) => r.data);
export const editSessionExercise = (id, order, body, actor, by) =>
  client
    .patch(`/sessions/${id}/exercise/${order}/edit`, body, {
      params: { ...(actor ? { actor } : {}), ...(by != null ? { by } : {}) },
    })
    .then((r) => r.data);
export const logSessionSet = (id, order, setIndex, body, actor, by) =>
  client
    .patch(`/sessions/${id}/exercise/${order}/set/${setIndex}`, body, {
      params: { ...(actor ? { actor } : {}), ...(by != null ? { by } : {}) },
    })
    .then((r) => r.data);
export const finishSession = (id) =>
  client.post(`/sessions/${id}/finish`).then((r) => r.data);
export const resumeSession = (id) =>
  client.post(`/sessions/${id}/resume`).then((r) => r.data);
export const pauseSession = (id, resume) =>
  client.post(`/sessions/${id}/pause`, null, { params: { resume } }).then((r) => r.data);

// --- Статистика ---
export const getStats = (telegramId) =>
  client.get(`/stats/${telegramId}`).then((r) => r.data);

// --- P7: подробная статистика (сбор с каждой тренировки) ---
export const getDetailedStats = (telegramId, params) =>
  client.get(`/stats/${telegramId}/detailed`, { params }).then((r) => r.data);
export const getExerciseProgress = (telegramId, params) =>
  client.get(`/stats/${telegramId}/exercise-progress`, { params }).then((r) => r.data);
export const getStreakData = (telegramId, params) =>
  client.get(`/stats/${telegramId}/streak`, { params }).then((r) => r.data);
export const getSessionDeviation = (sessionId) =>
  client.get(`/sessions/${sessionId}/deviation`).then((r) => r.data);
export const getPlanMissed = (planId) =>
  client.get(`/plans/${planId}/missed`).then((r) => r.data);
export const getCoachClientStats = (coachId, athleteId, params) =>
  client.get(`/coach/${coachId}/clients/${athleteId}/stats`, { params }).then((r) => r.data);
export const getCoachClientExerciseProgress = (coachId, athleteId, params) =>
  client.get(`/coach/${coachId}/clients/${athleteId}/exercise-progress`, { params }).then((r) => r.data);

// --- P2.1: пропуски / переносы тренировочных дней ---
export const skipPlanDay = (planId, body) =>
  client.post(`/plans/${planId}/day/skip`, body).then((r) => r.data);
export const reschedulePlanDay = (planId, body) =>
  client.post(`/plans/${planId}/day/reschedule`, body).then((r) => r.data);
export const markPlanDay = (planId, week, day, body) =>
  client.patch(`/plans/${planId}/day/${week}/${day}/mark`, body).then((r) => r.data);
export const unmarkPlanDay = (planId, week, day) =>
  client.delete(`/plans/${planId}/day/${week}/${day}/mark`).then((r) => r.data);
export const updateUserSettings = (telegramId, body) =>
  client.patch(`/users/${telegramId}/settings`, body).then((r) => r.data);

export const getTelegramAvatar = (userId) =>
  client.get(`/telegram/avatar/${userId}`).then((r) => r.data);

// --- Пользователь по telegram_id (для режима тренера) ---
export const getUserById = (telegramId) =>
  client.get(`/users/${telegramId}`).then((r) => r.data);

// --- P3: Режим тренера ---
export const switchMode = (telegramId, mode) =>
  client.patch(`/users/${telegramId}/mode`, { mode }).then((r) => r.data);
export const coachInvite = (coach_telegram_id) =>
  client.post(`/coach/invite`, { coach_telegram_id }).then((r) => r.data);
export const coachLink = (code, athlete_telegram_id) =>
  client.post(`/coach/link`, { code, athlete_telegram_id }).then((r) => r.data);
export const coachUnlink = (athlete_telegram_id) =>
  client.post(`/coach/unlink`, { athlete_telegram_id }).then((r) => r.data);
export const getCoachClients = (telegramId) =>
  client.get(`/coach/${telegramId}/clients`).then((r) => r.data);
export const getCoachClientPlan = (coachId, athleteId) =>
  client.get(`/coach/${coachId}/clients/${athleteId}/plan`).then((r) => r.data);
export const getCoachClientSession = (coachId, athleteId) =>
  client.get(`/coach/${coachId}/clients/${athleteId}/session`).then((r) => r.data);
export const getAthleteCoach = (telegramId) =>
  client.get(`/athlete/${telegramId}/coach`).then((r) => r.data);
export const setPlanVisibility = (planId, visibility) =>
  client.patch(`/plans/${planId}/visibility`, { visibility }).then((r) => r.data);
export const publishPlanWeek = (planId, week, published) =>
  client.patch(`/plans/${planId}/weeks/${week}/publish`, { published }).then((r) => r.data);
export const setPlanTrainingDays = (planId, training_days) =>
  client.patch(`/plans/${planId}/training-days`, { training_days }).then((r) => r.data);

// --- Редактор плана (тренер/владелец) ---
export const updatePlanMeta = (planId, body) =>
  client.patch(`/plans/${planId}`, body).then((r) => r.data);
export const upsertPlanDay = (planId, body) =>
  client.put(`/plans/${planId}/day`, body).then((r) => r.data);
export const deletePlanDay = (planId, week, day) =>
  client.delete(`/plans/${planId}/day`, { params: { week, day } }).then((r) => r.data);
export const upsertPlanExercise = (planId, body) =>
  client.put(`/plans/${planId}/exercise`, body).then((r) => r.data);
export const deletePlanExercise = (planId, week, day, order) =>
  client.delete(`/plans/${planId}/exercise`, { params: { week, day, order } }).then((r) => r.data);
export const addPlanWeek = (planId) =>
  client.post(`/plans/${planId}/week`).then((r) => r.data);
export const deletePlanWeek = (planId, week) =>
  client.delete(`/plans/${planId}/week`, { params: { week } }).then((r) => r.data);

export default client;
