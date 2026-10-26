const HOP_BY_HOP_HEADERS = ['connection', 'keep-alive', 'transfer-encoding', 'upgrade', 'host'];

function backendUrl(requestUrl, apiOrigin) {
  const incoming = new URL(requestUrl);
  const target = new URL(incoming.pathname + incoming.search, apiOrigin);
  return target.toString();
}

function forwardedHeaders(request) {
  const headers = new Headers(request.headers);
  for (const name of HOP_BY_HOP_HEADERS) {
    headers.delete(name);
  }
  headers.set('X-Forwarded-Host', new URL(request.url).host);
  headers.set('X-Forwarded-Proto', 'https');
  return headers;
}

function hasBody(method) {
  return method !== 'GET' && method !== 'HEAD';
}

export async function onRequest({ request, env }) {
  if (!env.API_ORIGIN) {
    return Response.json({ error: 'API_ORIGIN não configurado.' }, { status: 500 });
  }

  try {
    return await fetch(backendUrl(request.url, env.API_ORIGIN), {
      method: request.method,
      headers: forwardedHeaders(request),
      body: hasBody(request.method) ? request.body : undefined,
      duplex: 'half',
      redirect: 'manual',
    });
  } catch (error) {
    console.error(error);
    return Response.json({ error: 'Não foi possível falar com o servidor.' }, { status: 502 });
  }
}
