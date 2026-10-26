import { apiRequest, fetchSession } from '../api.js';
import { byId, onSubmit, runPage } from '../render.js';
import { homeFor } from '../session.js';

async function submitSetup(fields) {
  const session = await apiRequest('/api/setup', {
    method: 'POST',
    body: { username: fields.get('username'), password: fields.get('password') },
  });
  window.location.replace(homeFor(session.user));
}

runPage(async () => {
  const session = await fetchSession();
  if (!session.needs_setup) {
    window.location.replace('/login.html');
    return;
  }
  onSubmit(byId('setup-form'), byId('page-error'), submitSetup);
});
