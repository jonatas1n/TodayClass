import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';

import { onRequest } from '../functions/api/[[path]].js';

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function captureFetch(response) {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return response;
  };
  return calls;
}

test('forwards path, query, method, cookie and body to the backend', async () => {
  const calls = captureFetch(new Response('{}', { status: 201 }));
  const request = new Request('https://todayclass.pages.dev/api/courses?page=2', {
    method: 'POST',
    headers: { Cookie: 'session=abc', 'X-CSRF-Token': 'token', 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: 'Curso' }),
  });

  const response = await onRequest({ request, env: { API_ORIGIN: 'https://todayclass-api.vercel.app' } });

  assert.equal(response.status, 201);
  assert.equal(calls.length, 1);
  const { url, init } = calls[0];
  assert.equal(url, 'https://todayclass-api.vercel.app/api/courses?page=2');
  assert.equal(init.method, 'POST');
  assert.equal(init.headers.get('cookie'), 'session=abc');
  assert.equal(init.headers.get('x-csrf-token'), 'token');
  assert.equal(init.headers.get('host'), null);
  assert.equal(init.headers.get('x-forwarded-host'), 'todayclass.pages.dev');
  assert.ok(init.body);
});

test('does not send a body for GET requests', async () => {
  const calls = captureFetch(new Response('{}'));
  const request = new Request('https://todayclass.pages.dev/api/session');

  await onRequest({ request, env: { API_ORIGIN: 'https://todayclass-api.vercel.app' } });

  assert.equal(calls[0].init.method, 'GET');
  assert.equal(calls[0].init.body, undefined);
});

test('returns the backend response with its Set-Cookie header', async () => {
  captureFetch(new Response('{}', { headers: { 'Set-Cookie': 'session=new; HttpOnly; Secure' } }));
  const request = new Request('https://todayclass.pages.dev/api/login', { method: 'POST', body: '{}' });

  const response = await onRequest({ request, env: { API_ORIGIN: 'https://todayclass-api.vercel.app' } });

  assert.equal(response.headers.get('set-cookie'), 'session=new; HttpOnly; Secure');
});

test('answers 500 when API_ORIGIN is missing', async () => {
  const calls = captureFetch(new Response('{}'));
  const request = new Request('https://todayclass.pages.dev/api/session');

  const response = await onRequest({ request, env: {} });

  assert.equal(response.status, 500);
  assert.equal(calls.length, 0);
});

test('answers 502 when the backend cannot be reached', async () => {
  globalThis.fetch = async () => {
    throw new TypeError('network down');
  };
  const originalConsoleError = console.error;
  console.error = () => {};
  const request = new Request('https://todayclass.pages.dev/api/session');

  try {
    const response = await onRequest({ request, env: { API_ORIGIN: 'https://todayclass-api.vercel.app' } });
    assert.equal(response.status, 502);
    assert.deepEqual(await response.json(), { error: 'Não foi possível falar com o servidor.' });
  } finally {
    console.error = originalConsoleError;
  }
});
