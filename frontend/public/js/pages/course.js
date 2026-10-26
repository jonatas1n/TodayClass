import { ApiError, apiRequest } from '../api.js';
import { byId, element, formatTimestamp, icon, lessonCountLabel, queryNumber, runPage, statusBadge } from '../render.js';
import { requireSession } from '../session.js';

function lessonUrl(lesson) {
  return `/lesson.html?course=${lesson.course_id}&lesson=${lesson.id}`;
}

function editLessonUrl(lesson) {
  return `/lesson-form.html?course=${lesson.course_id}&lesson=${lesson.id}`;
}

function lessonBody(lesson) {
  const body = element('span', { className: 'lesson-row__body' }, [
    element('span', { className: 'lesson-row__title', text: lesson.label }),
  ]);
  if (lesson.completed_at) {
    body.append(element('span', {
      className: 'lesson-row__meta',
      text: `Concluída em ${formatTimestamp(lesson.completed_at)}`,
    }));
  }
  return body;
}

function lessonRow(lesson, isAdmin) {
  const rowClass = lesson.is_completed ? 'lesson-row lesson-row--completed' : 'lesson-row';
  const marker = element('span', { className: 'lesson-row__marker', attributes: { 'aria-hidden': 'true' } }, [
    icon(lesson.is_completed ? 'circle-check' : 'circle'),
  ]);
  const link = element('a', { className: rowClass, attributes: { href: lessonUrl(lesson) } }, [
    element('span', { className: 'lesson-row__main' }, [marker, lessonBody(lesson)]),
    statusBadge(lesson.is_completed),
  ]);

  const item = element('li', { className: 'lesson-list__item' }, [link]);
  if (isAdmin) {
    item.append(element('a', { className: 'lesson-list__edit', attributes: { href: editLessonUrl(lesson) } }, [
      icon('pencil'),
      'Editar',
    ]));
  }
  return item;
}

function emptyLessons() {
  return element('div', { className: 'list-panel' }, [
    element('div', { className: 'empty-state' }, [
      icon('book-open', 'empty-state__icon'),
      element('p', { className: 'empty-state__title', text: 'Nenhuma aula ainda.' }),
    ]),
  ]);
}

function renderProgress(lessons) {
  const completedCount = lessons.filter((lesson) => lesson.is_completed).length;
  byId('progress-summary').textContent = `${completedCount} de ${lessons.length} concluídas`;
  const bar = byId('progress-bar');
  bar.max = lessons.length || 1;
  bar.value = completedCount;
  bar.textContent = `${completedCount} de ${lessons.length}`;
}

function renderLessons(lessons, isAdmin) {
  byId('lesson-total').textContent = lessonCountLabel(lessons.length);
  if (lessons.length === 0) {
    byId('lesson-panel').replaceChildren(emptyLessons());
    return;
  }
  const list = element('ul', { className: 'lesson-list' }, lessons.map((lesson) => lessonRow(lesson, isAdmin)));
  byId('lesson-panel').replaceChildren(list);
}

runPage(async () => {
  const session = await requireSession();
  const courseId = queryNumber('course');
  if (courseId === null) {
    throw new ApiError('Curso não encontrado.', 404);
  }

  const { course } = await apiRequest(`/api/courses/${courseId}`);
  const isAdmin = session.user.role === 'admin';
  document.title = `${course.name} · TodayClass`;
  byId('course-name').textContent = course.name;
  byId('course-actions').hidden = !isAdmin;
  byId('new-lesson-button').href = `/lesson-form.html?course=${course.id}`;
  renderProgress(course.lessons);
  renderLessons(course.lessons, isAdmin);
  byId('course-content').hidden = false;
});
