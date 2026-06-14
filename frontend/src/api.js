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

export default client;
