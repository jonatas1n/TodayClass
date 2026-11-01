import { ApiError, apiRequest } from '../api.js';
import { byId, element, formatTimestamp, hideLoading, icon, lessonCountLabel, onSubmit, queryNumber, refreshIcons, runPage, statusBadge } from '../render.js';
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

function lessonIsOpen(lesson) {
  return lesson.is_available !== false;
}

function lessonRow(lesson, isAdmin) {
  const open = isAdmin || lessonIsOpen(lesson);
  const rowClass = open ? 'lesson-row' : 'lesson-row lesson-row--locked';
  const completedClass = lesson.is_completed ? ' lesson-row--completed' : '';
  const markerName = lesson.is_completed ? 'circle-check' : 'circle';
  const marker = element('span', { className: 'lesson-row__marker', attributes: { 'aria-hidden': 'true' } }, [
    icon(open ? markerName : 'lock'),
  ]);
  const body = lessonBody(lesson);
  if (!open && lesson.unavailable_reason) {
    body.append(element('span', { className: 'lesson-row__meta', text: lesson.unavailable_reason }));
  }
  const row = element(open ? 'a' : 'div', {
    className: `${rowClass}${completedClass}`,
    attributes: open ? { href: lessonUrl(lesson) } : {},
  }, [
    element('span', { className: 'lesson-row__main' }, [marker, body]),
  ]);
  if (open) {
    row.append(statusBadge(lesson.is_completed));
  }
  const item = element('li', { className: 'lesson-list__item' }, [row]);
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

function statusNote(course) {
  if (course.completed_on) {
    const [year, month, day] = course.completed_on.split('-');
    return `Curso concluído em ${day}/${month}/${year}.`;
  }
  const hasBlankAnswer = course.questions.some((question) => question.answer.trim() === '');
  if (hasBlankAnswer) {
    return 'Responda as perguntas para concluir o curso.';
  }
  return '';
}

function renderStatus(course) {
  const note = byId('course-status');
  const message = statusNote(course);
  note.textContent = message;
  note.hidden = message === '';
}

function textArea(name, value, maxLength, className) {
  const field = element('textarea', {
    className,
    attributes: { name, maxlength: String(maxLength) },
  });
  field.value = value;
  return field;
}

function answerText(question) {
  if (question.answer.trim() === '') {
    return element('p', { className: 'question-answer question-answer--empty', text: 'Ainda sem resposta.' });
  }
  return element('p', { className: 'question-answer', text: question.answer });
}

function adminQuestionBlock(question) {
  const prompt = element('label', { text: 'Pergunta' }, [
    textArea('prompt', question.prompt, 500, 'textarea--question'),
  ]);
  const remove = element('label', {}, [
    element('input', { attributes: { type: 'checkbox', name: 'remove' } }),
    ' Remover',
  ]);
  return element('div', { className: 'question-block', attributes: { 'data-question-id': String(question.id) } }, [
    prompt,
    element('p', { className: 'form-section__hint', text: 'Resposta do aluno' }),
    answerText(question),
    remove,
  ]);
}

function studentQuestionBlock(question) {
  return element('div', { className: 'question-block', attributes: { 'data-question-id': String(question.id) } }, [
    element('p', { className: 'question-block__prompt', text: question.prompt }),
    element('label', { text: 'Resposta' }, [
      textArea('answer', question.answer, 4000),
    ]),
  ]);
}

function questionChanges(form) {
  return [...form.querySelectorAll('[data-question-id]')].map((block) => ({
    id: Number(block.dataset.questionId),
    prompt: block.querySelector('[name="prompt"]').value,
    remove: block.querySelector('[name="remove"]').checked,
  }));
}

function answerChanges(form) {
  return [...form.querySelectorAll('[data-question-id]')].map((block) => ({
    id: Number(block.dataset.questionId),
    answer: block.querySelector('[name="answer"]').value,
  }));
}

function renderQuestions(course, isAdmin, showCourse) {
  const section = byId('question-section');
  if (!isAdmin && course.questions.length === 0) {
    section.hidden = true;
    byId('question-panel').replaceChildren();
    return;
  }

  const blocks = course.questions.map((question) => (
    isAdmin ? adminQuestionBlock(question) : studentQuestionBlock(question)
  ));
  const form = element('form', { className: 'form-stack' }, blocks);
  if (isAdmin) {
    form.append(
      element('label', { text: 'Nova pergunta' }, [
        textArea('new_prompt', '', 500, 'textarea--question'),
      ]),
      element('p', { className: 'form-section__hint', text: 'Opcional. Deixe em branco para não adicionar.' }),
    );
  }
  form.append(element('div', { className: 'form-actions' }, [
    element('button', { attributes: { type: 'submit' } }, [
      icon('check'),
      isAdmin ? 'Salvar perguntas' : 'Salvar respostas',
    ]),
  ]));

  onSubmit(form, byId('page-error'), async () => {
    const path = isAdmin ? `/api/courses/${course.id}/questions` : `/api/courses/${course.id}/answers`;
    const body = isAdmin
      ? { questions: questionChanges(form), new_prompt: form.querySelector('[name="new_prompt"]').value }
      : { answers: answerChanges(form) };
    const payload = await apiRequest(path, { method: 'POST', body });
    showCourse(payload.course);
  });

  byId('question-panel').replaceChildren(form);
  section.hidden = false;
}

function showCourse(course, isAdmin) {
  document.title = `${course.name} · DiáriaMente`;
  byId('course-name').textContent = course.name;
  byId('course-actions').hidden = !isAdmin;
  byId('edit-course-button').href = `/edit-course.html?course=${course.id}`;
  byId('new-lesson-button').href = `/lesson-form.html?course=${course.id}`;
  renderProgress(course.lessons);
  renderStatus(course);
  renderLessons(course.lessons, isAdmin);
  renderQuestions(course, isAdmin, (updated) => showCourse(updated, isAdmin));
  hideLoading(byId('course-loading'));
  byId('course-content').hidden = false;
  refreshIcons();
}

async function loadCourse(courseId) {
  try {
    return await apiRequest(`/api/courses/${courseId}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      window.location.replace('/courses.html');
      return null;
    }
    throw error;
  }
}

runPage(async () => {
  const session = await requireSession();
  const courseId = queryNumber('course');
  if (courseId === null) {
    throw new ApiError('Curso não encontrado.', 404);
  }

  const payload = await loadCourse(courseId);
  if (payload === null) {
    return;
  }
  showCourse(payload.course, session.user.role === 'admin');
});
