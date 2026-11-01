import { apiRequest, fetchSession, loginUrl } from './api.js';
import { byId, element, icon } from './render.js';

const ADMIN_ROLE = 'admin';

export function homeFor(user) {
  return user.role === ADMIN_ROLE ? '/admin.html' : '/courses.html';
}

export function safeNextPath(rawNext) {
  if (!rawNext || !rawNext.startsWith('/') || rawNext.startsWith('//')) {
    return null;
  }
  return rawNext;
}

function navLink(href, iconName, label, isCurrent) {
  const attributes = { href };
  if (isCurrent) {
    attributes['aria-current'] = 'page';
  }
  return element('a', { className: 'site-nav__link', attributes }, [icon(iconName), label]);
}

async function logout() {
  await apiRequest('/api/logout', { method: 'POST' });
  window.location.replace('/login.html');
}

function logoutButton() {
  const button = element('button', { className: 'site-header__logout', attributes: { type: 'button' } }, [
    icon('log-out'),
    'Sair',
  ]);
  button.addEventListener('click', () => {
    logout().catch((error) => {
      console.error(error);
      window.location.replace('/login.html');
    });
  });
  return button;
}

function renderHeader(user) {
  const section = document.body.dataset.section;
  const links = [navLink('/courses.html', 'book-open', 'Cursos', section === 'courses')];
  if (user.role === ADMIN_ROLE) {
    links.push(navLink('/admin.html', 'chart-column', 'Progresso', section === 'progress'));
  }

  const nav = byId('site-nav');
  nav.replaceChildren(...links);
  nav.hidden = false;

  const avatar = element('span', {
    className: 'site-header__avatar',
    text: user.username.slice(0, 1),
    attributes: { title: user.username, 'aria-hidden': 'true' },
  });
  const actions = byId('site-actions');
  actions.replaceChildren(logoutButton(), avatar);
  actions.hidden = false;

  byId('site-brand').setAttribute('href', homeFor(user));
}

// Resolves only for an allowed user; otherwise it redirects and never resolves, so the page stops rendering.
export async function requireSession({ role } = {}) {
  const session = await fetchSession();
  if (!session.user) {
    window.location.replace(loginUrl());
    return new Promise(() => {});
  }
  if (role && session.user.role !== role) {
    window.location.replace(homeFor(session.user));
    return new Promise(() => {});
  }
  renderHeader(session.user);
  return session;
}
