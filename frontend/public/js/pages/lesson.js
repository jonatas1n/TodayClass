import { ApiError, apiRequest } from '../api.js';
import { byId, element, formatTimestamp, icon, queryNumber, refreshIcons, runPage, setBusy, showError } from '../render.js';
import { requireSession } from '../session.js';

function lessonApiPath(courseId, lessonId) {
  return `/api/courses/${courseId}/lessons/${lessonId}`;
}

function linkItem(link) {
  const anchor = element('a', {
    className: 'resource-links__link',
    text: link.title,
    attributes: { href: link.url, target: '_blank', rel: 'noopener' },
  });
  anchor.append(icon('arrow-up-right'));
  return element('li', {}, [anchor]);
}

function completionBadge(lesson) {
  const label = lesson.completed_at ? `Concluída em ${formatTimestamp(lesson.completed_at)}` : 'Concluída';
  return element('span', { className: 'completion-badge' }, [icon('circle-check'), label]);
}

function pendingNote() {
  return element('p', { className: 'completion-note' }, [icon('circle'), 'Ainda não concluída.']);
}

function completeButton(lesson) {
  const button = element('button', { attributes: { type: 'button' } }, [icon('check'), 'Marcar como feita']);
  const action = element('div', { className: 'lesson-status__action' }, [button]);
  button.addEventListener('click', async () => {
    setBusy(action, true);
    try {
      await apiRequest(`${lessonApiPath(lesson.course_id, lesson.id)}/complete`, { method: 'POST' });
      window.location.assign('/success.html');
    } catch (error) {
      console.error(error);
      showError(byId('page-error'), error.message);
      setBusy(action, false);
    }
  });
  return action;
}

function statusContent(lesson, role) {
  if (lesson.is_completed) {
    return completionBadge(lesson);
  }
  if (role === 'student') {
    return completeButton(lesson);
  }
  return pendingNote();
}

function renderLinks(links) {
  if (links.length === 0) {
    return;
  }
  byId('lesson-link-list').replaceChildren(...links.map(linkItem));
  byId('lesson-links').hidden = false;
}

function renderNavigation(lesson, role) {
  const courseLink = byId('course-link');
  courseLink.href = `/course.html?course=${lesson.course_id}`;
  byId('course-link-label').textContent = lesson.course_name;

  if (role !== 'admin') {
    return;
  }
  const editButton = byId('edit-lesson-button');
  editButton.href = `/lesson-form.html?course=${lesson.course_id}&lesson=${lesson.id}`;
  editButton.hidden = false;
}

runPage(async () => {
  const session = await requireSession();
  const courseId = queryNumber('course');
  const lessonId = queryNumber('lesson');
  if (courseId === null || lessonId === null) {
    throw new ApiError('Aula não encontrada.', 404);
  }

  const { lesson } = await apiRequest(lessonApiPath(courseId, lessonId));
  const role = session.user.role;
  document.title = `${lesson.label} · TodayClass`;
  renderNavigation(lesson, role);
  byId('lesson-course-name').textContent = lesson.course_name;
  byId('lesson-label').textContent = lesson.label;
  byId('lesson-content').innerHTML = lesson.content;
  renderLinks(lesson.links);
  byId('lesson-status').replaceChildren(statusContent(lesson, role));
  byId('lesson-article').hidden = false;
  refreshIcons();
});
