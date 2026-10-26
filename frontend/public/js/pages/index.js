import { fetchSession } from '../api.js';
import { runPage } from '../render.js';
import { homeFor } from '../session.js';

runPage(async () => {
  const session = await fetchSession();
  if (!session.user) {
    window.location.replace('/login.html');
    return;
  }
  window.location.replace(homeFor(session.user));
});
