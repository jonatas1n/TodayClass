import { ApiError, apiRequest } from '../api.js';
import { byId, element, icon, onSubmit, queryNumber, runPage } from '../render.js';
import { requireSession } from '../session.js';

const LINK_ROW_COUNT = 4;

function linkInput(labelText, attributes) {
  return element('label', {}, [labelText, element('input', { attributes })]);
}

function linkRow(link) {
  return element('div', { className: 'link-row' }, [
    linkInput('Título', { type: 'text', name: 'link_title', maxlength: '100', value: link?.title ?? '' }),
    linkInput('URL', { type: 'url', name: 'link_url', maxlength: '255', value: link?.url ?? '' }),
  ]);
}

function renderLinkRows(links) {
  const rows = Array.from({ length: LINK_ROW_COUNT }, (_, index) => linkRow(links[index]));
  byId('link-rows').replaceChildren(...rows);
}

function fillLessonFields(form, lesson) {
  form.elements.day.value = lesson.day;
  form.elements.title.value = lesson.title;
  form.elements.content.value = lesson.content;
}

function linksFromFields(fields) {
  const titles = fields.getAll('link_title');
  const urls = fields.getAll('link_url');
  return titles.map((title, index) => ({ title, url: urls[index] ?? '' }));
}

function lessonBody(fields) {
  return {
    day: fields.get('day'),
    title: fields.get('title'),
    content: fields.get('content'),
    links: linksFromFields(fields),
  };
}

function renderFormHeader(course, lesson) {
  const isEditing = lesson !== null;
  const pageTitle = isEditing ? `Editar ${lesson.label}` : 'Nova aula';
  const courseUrl = `/course.html?course=${course.id}`;

  document.title = `${pageTitle} · TodayClass`;
  byId('course-link').href = courseUrl;
  byId('course-link-label').textContent = course.name;
  byId('course-name').textContent = course.name;
  byId('form-title').textContent = pageTitle;
  byId('cancel-link').href = isEditing ? `/lesson.html?course=${course.id}&lesson=${lesson.id}` : courseUrl;
  byId('submit-button').replaceChildren(
    icon(isEditing ? 'check' : 'plus'),
    isEditing ? 'Salvar' : 'Criar aula',
  );
}

async function loadLesson(courseId, lessonId) {
  if (lessonId === null) {
    return null;
  }
  const { lesson } = await apiRequest(`/api/courses/${courseId}/lessons/${lessonId}`);
  return lesson;
}

function saveLesson(courseId, lessonId, body) {
  const lessonsPath = `/api/courses/${courseId}/lessons`;
  if (lessonId === null) {
    return apiRequest(lessonsPath, { method: 'POST', body });
  }
  return apiRequest(`${lessonsPath}/${lessonId}`, { method: 'PUT', body });
}

runPage(async () => {
  await requireSession({ role: 'admin' });
  const courseId = queryNumber('course');
  const lessonId = queryNumber('lesson');
  if (courseId === null) {
    throw new ApiError('Curso não encontrado.', 404);
  }

  const [{ course }, lesson] = await Promise.all([
    apiRequest(`/api/courses/${courseId}`),
    loadLesson(courseId, lessonId),
  ]);

  const form = byId('lesson-form');
  renderFormHeader(course, lesson);
  renderLinkRows(lesson?.links ?? []);
  if (lesson) {
    fillLessonFields(form, lesson);
  }

  onSubmit(form, byId('form-error'), async (fields) => {
    const { lesson: savedLesson } = await saveLesson(courseId, lessonId, lessonBody(fields));
    window.location.assign(`/lesson.html?course=${courseId}&lesson=${savedLesson.id}`);
  });
  byId('form-content').hidden = false;
});
