import { apiRequest, fetchSession } from '../api.js';
import { byId, onSubmit, runPage } from '../render.js';
import { homeFor, safeNextPath } from '../session.js';

function destinationAfterLogin(user) {
  const next = safeNextPath(new URLSearchParams(window.location.search).get('next'));
  return next ?? homeFor(user);
}

async function submitLogin(fields) {
  const session = await apiRequest('/api/login', {
    method: 'POST',
    body: { username: fields.get('username'), password: fields.get('password') },
    redirectOnUnauthorized: false,
  });
  window.location.replace(destinationAfterLogin(session.user));
}

runPage(async () => {
  const session = await fetchSession();
  if (session.user) {
    window.location.replace(destinationAfterLogin(session.user));
    return;
  }
  byId('setup-link').hidden = !session.needs_setup;
  onSubmit(byId('login-form'), byId('page-error'), submitLogin);
});
