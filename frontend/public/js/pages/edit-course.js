import { ApiError, apiRequest } from '../api.js';
import { byId, onSubmit, queryNumber, runPage } from '../render.js';
import { requireSession } from '../session.js';

function coursePage(courseId) {
  return `/course.html?course=${courseId}`;
}

runPage(async () => {
  await requireSession({ role: 'admin' });
  const courseId = queryNumber('course');
  if (courseId === null) {
    throw new ApiError('Curso não encontrado.', 404);
  }

  const { course } = await apiRequest(`/api/courses/${courseId}`);
  byId('course-name').value = course.name;
  byId('back-link').href = coursePage(course.id);
  byId('cancel-link').href = coursePage(course.id);
  document.title = 'Editar curso · DiáriaMente';

  onSubmit(byId('course-form'), byId('page-error'), async (fields) => {
    const payload = await apiRequest(`/api/courses/${course.id}`, {
      method: 'PUT',
      body: { name: fields.get('name') },
    });
    window.location.assign(coursePage(payload.course.id));
  });
});
