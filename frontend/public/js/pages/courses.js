import { apiRequest } from '../api.js';
import { byId, element, icon, lessonCountLabel, releaseLoading, runPage } from '../render.js';
import { requireSession } from '../session.js';

function emptyState() {
  return element('div', { className: 'empty-state' }, [
    icon('book-open', 'empty-state__icon'),
    element('p', { className: 'empty-state__title', text: 'Nenhum curso ainda.' }),
  ]);
}

function courseSubtitle(course) {
  if (course.completed_at) {
    return 'Concluído';
  }
  return null;
}

function courseRow(course) {
  const subtitle = courseSubtitle(course);
  const body = [
    element('span', { className: 'course-row__title', text: course.name }),
  ];
  if (subtitle) {
    body.push(element('span', { className: 'course-row__subtitle', text: subtitle }));
  }
  const row = element('a', {
    className: 'course-row',
    attributes: { href: `/course.html?course=${course.id}` },
  }, [
    element('span', { className: 'course-row__icon', text: course.name.slice(0, 1), attributes: { 'aria-hidden': 'true' } }),
    element('span', { className: 'course-row__body' }, body),
    element('span', { className: 'course-row__meta' }, [lessonCountLabel(course.lesson_count), icon('chevron-right')]),
  ]);
  return element('li', {}, [row]);
}

function courseList(courses) {
  const head = element('div', { className: 'list-panel__head' }, [
    element('span', { text: 'Curso' }),
    element('span', { text: 'Aulas' }),
  ]);
  return [head, element('ul', { className: 'course-list' }, courses.map(courseRow))];
}

function totalLessonCount(courses) {
  return courses.reduce((total, course) => total + course.lesson_count, 0);
}

function showCourseCounts(courses) {
  byId('course-count').textContent = String(courses.length);
  byId('lesson-count').textContent = String(totalLessonCount(courses));
  releaseLoading(byId('course-stats'));
}

function renderCoursePanel(courses) {
  const panel = byId('course-panel');
  if (courses.length === 0) {
    panel.replaceChildren(emptyState());
    releaseLoading(panel);
    return;
  }
  panel.replaceChildren(...courseList(courses));
  releaseLoading(panel);
}

runPage(async () => {
  const session = await requireSession();
  const { courses } = await apiRequest('/api/courses');
  showCourseCounts(courses);
  byId('new-course-button').hidden = session.user.role !== 'admin';
  renderCoursePanel(courses);
});
