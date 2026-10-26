import { apiRequest } from '../api.js';
import { byId, element, icon, lessonCountLabel, runPage } from '../render.js';
import { requireSession } from '../session.js';

function emptyState() {
  return element('div', { className: 'empty-state' }, [
    icon('book-open', 'empty-state__icon'),
    element('p', { className: 'empty-state__title', text: 'Nenhum curso ainda.' }),
  ]);
}

function courseRow(course) {
  const link = element('a', { className: 'course-row', attributes: { href: `/course.html?course=${course.id}` } }, [
    element('span', { className: 'course-row__icon', text: course.name.slice(0, 1), attributes: { 'aria-hidden': 'true' } }),
    element('span', { className: 'course-row__body' }, [
      element('span', { className: 'course-row__title', text: course.name }),
    ]),
    element('span', { className: 'course-row__meta' }, [lessonCountLabel(course.lesson_count), icon('chevron-right')]),
  ]);
  return element('li', {}, [link]);
}

function courseList(courses) {
  const head = element('div', { className: 'list-panel__head' }, [
    element('span', { text: 'Curso' }),
    element('span', { text: 'Aulas' }),
  ]);
  return [head, element('ul', { className: 'course-list' }, courses.map(courseRow))];
}

runPage(async () => {
  const session = await requireSession();
  const { courses } = await apiRequest('/api/courses');

  byId('course-count').textContent = courses.length;
  byId('lesson-count').textContent = courses.reduce((total, course) => total + course.lesson_count, 0);
  byId('new-course-button').hidden = session.user.role !== 'admin';

  const panel = byId('course-panel');
  if (courses.length === 0) {
    panel.replaceChildren(emptyState());
    return;
  }
  panel.replaceChildren(...courseList(courses));
});
