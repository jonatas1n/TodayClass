const DEFAULT_ERROR_MESSAGE = 'Não foi possível concluir o pedido.';

let csrfToken = null;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function loginUrl() {
  const next = `${window.location.pathname}${window.location.search}`;
  return `/login.html?next=${encodeURIComponent(next)}`;
}

async function readJson(response) {
  const contentType = response.headers.get('Content-Type') ?? '';
  if (!contentType.includes('application/json')) {
    return null;
  }
  return response.json();
}

function requestOptions(method, body) {
  const options = {
    method,
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  };
  if (method === 'GET') {
    return options;
  }
  options.headers['Content-Type'] = 'application/json';
  options.headers['X-CSRF-Token'] = csrfToken ?? '';
  options.body = JSON.stringify(body ?? {});
  return options;
}

export async function apiRequest(path, { method = 'GET', body, redirectOnUnauthorized = true } = {}) {
  const response = await fetch(path, requestOptions(method, body));
  const payload = await readJson(response);

  if (payload?.csrf_token) {
    csrfToken = payload.csrf_token;
  }
  if (response.ok) {
    return payload;
  }
  if (response.status === 401 && redirectOnUnauthorized) {
    window.location.replace(loginUrl());
  }
  throw new ApiError(payload?.error ?? DEFAULT_ERROR_MESSAGE, response.status);
}

export function fetchSession() {
  return apiRequest('/api/session', { redirectOnUnauthorized: false });
}
