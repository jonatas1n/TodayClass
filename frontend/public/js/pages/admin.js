import { apiRequest } from '../api.js';
import { byId, element, formatTimestamp, icon, onSubmit, refreshIcons, runPage, statusBadge } from '../render.js';
import { requireSession } from '../session.js';

function progressRow(lesson) {
  const courseLink = element('a', { text: lesson.course_name, attributes: { href: `/course.html?course=${lesson.course_id}` } });
  const lessonLink = element('a', {
    text: lesson.label,
    attributes: { href: `/lesson.html?course=${lesson.course_id}&lesson=${lesson.id}` },
  });
  return element('tr', {}, [
    element('td', {}, [courseLink]),
    element('td', {}, [lessonLink]),
    element('td', {}, [statusBadge(lesson.is_completed)]),
    element('td', { className: 'data-table__mono', text: formatTimestamp(lesson.completed_at) }),
    element('td', { className: 'data-table__numeric', text: lesson.link_count }),
  ]);
}

function emptyProgressRow() {
  return element('tr', {}, [element('td', { text: 'Nenhuma aula ainda.', attributes: { colspan: '5' } })]);
}

function roleTag(role) {
  if (role === 'admin') {
    return element('span', { className: 'tag tag--primary', text: 'administrador' });
  }
  return element('span', { className: 'tag', text: 'aluno' });
}

function passwordForm(user) {
  const form = element('form', { className: 'inline-form' }, [
    element('label', {}, [
      'Nova senha',
      element('input', {
        attributes: { type: 'password', name: 'password', autocomplete: 'new-password', minlength: '8', required: '' },
      }),
    ]),
    element('button', { className: 'button--secondary', attributes: { type: 'submit' } }, [
      icon('key-round'),
      'Definir senha',
    ]),
  ]);
  const errorContainer = element('div', { attributes: { hidden: '' } });
  onSubmit(form, errorContainer, async (fields) => {
    await apiRequest(`/api/admin/users/${user.id}/password`, {
      method: 'PUT',
      body: { password: fields.get('password') },
    });
    form.reset();
  });
  return [errorContainer, form];
}

function userRow(user) {
  return element('div', { className: 'user-row' }, [
    element('div', { className: 'user-row__header' }, [
      element('span', { className: 'user-row__name', text: user.username }),
      roleTag(user.role),
    ]),
    ...passwordForm(user),
  ]);
}

async function renderProgress() {
  const { lessons } = await apiRequest('/api/admin/progress');
  const rows = lessons.length === 0 ? [emptyProgressRow()] : lessons.map(progressRow);
  byId('progress-rows').replaceChildren(...rows);
}

async function renderUsers() {
  const { users } = await apiRequest('/api/admin/users');
  byId('user-list').replaceChildren(...users.map(userRow));
  refreshIcons();
}

async function createUser(form, fields) {
  await apiRequest('/api/admin/users', {
    method: 'POST',
    body: { username: fields.get('username'), password: fields.get('password'), role: fields.get('role') },
  });
  form.reset();
  await renderUsers();
}

runPage(async () => {
  await requireSession({ role: 'admin' });
  await Promise.all([renderProgress(), renderUsers()]);

  const form = byId('new-user-form');
  onSubmit(form, byId('new-user-error'), (fields) => createUser(form, fields));
});
