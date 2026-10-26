import { apiRequest } from '../api.js';
import { byId, onSubmit, runPage } from '../render.js';
import { requireSession } from '../session.js';

async function submitCourse(fields) {
  const { course } = await apiRequest('/api/courses', {
    method: 'POST',
    body: { name: fields.get('name') },
  });
  window.location.assign(`/course.html?course=${course.id}`);
}

runPage(async () => {
  await requireSession({ role: 'admin' });
  onSubmit(byId('course-form'), byId('page-error'), submitCourse);
});
