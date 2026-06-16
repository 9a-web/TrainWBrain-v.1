import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Bearer-token auth (works across web, Telegram WebView and PWA). We deliberately
// do NOT use withCredentials so that CORS "*" stays valid (cannot combine "*"
// with credentials). The session cookie set by the backend is an unused bonus.
const client = axios.create({ baseURL: API });

// --- Auth token (Bearer) ---
const TOKEN_KEY = "twb_token";
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

// --- Планы ---
export const createPlan = (payload) =>
  client.post(`/plans`, payload).then((r) => r.data);
export const getActivePlan = (telegramId) =>
  client.get(`/plans/active/${telegramId}`).then((r) => r.data);
export const getPlan = (id) =>
  client.get(`/plans/${id}`).then((r) => r.data);
export const getPlanDay = (id, week, day) =>
  client.get(`/plans/${id}/day`, { params: { week, day } }).then((r) => r.data);
export const getWeekProgress = (id, week) =>
  client.get(`/plans/${id}/week-progress`, { params: { week } }).then((r) => r.data);

// --- Тренировочные сессии (Phase 2) ---
export const startSession = (payload) =>
  client.post(`/sessions/start`, payload).then((r) => r.data);
export const getSession = (id) =>
  client.get(`/sessions/${id}`).then((r) => r.data);
export const getActiveSession = (params) =>
  client.get(`/sessions/active`, { params }).then((r) => r.data);
export const sessionExerciseAction = (id, order, action) =>
  client.patch(`/sessions/${id}/exercise/${order}`, null, { params: { action } }).then((r) => r.data);
export const editSessionExercise = (id, order, body) =>
  client.patch(`/sessions/${id}/exercise/${order}/edit`, body).then((r) => r.data);
export const finishSession = (id) =>
  client.post(`/sessions/${id}/finish`).then((r) => r.data);
export const pauseSession = (id, resume) =>
  client.post(`/sessions/${id}/pause`, null, { params: { resume } }).then((r) => r.data);

// --- Статистика ---
export const getStats = (telegramId) =>
  client.get(`/stats/${telegramId}`).then((r) => r.data);

export const getTelegramAvatar = (userId) =>
  client.get(`/telegram/avatar/${userId}`).then((r) => r.data);

export default client;
