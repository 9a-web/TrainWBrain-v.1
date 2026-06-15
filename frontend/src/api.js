import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

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
