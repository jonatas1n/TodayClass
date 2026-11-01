from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from todayclass.models import Course, db
from todayclass.schedule import course_availability, course_requirements_met

VALID_LESSON = {
    'day': '2',
    'title': 'Aula 2',
    'content': '<p>Conteúdo</p>',
    'links': [],
}


def add_question(admin_api, prompt='Qual é a capital?'):
    response = admin_api.post('/api/courses/1/questions', {'questions': [], 'new_prompt': prompt})
    assert response.status_code == 200
    return response.get_json()['course']['questions'][-1]


def test_admin_renames_course(admin_api):
    response = admin_api.put('/api/courses/1', {'name': '  Português  '})

    assert response.status_code == 200
    assert response.get_json()['course']['name'] == 'Português'


def test_blank_rename_is_rejected(admin_api):
    response = admin_api.put('/api/courses/1', {'name': '   '})

    assert response.status_code == 400
    assert response.get_json()['error'] == 'O nome é obrigatório.'
    assert admin_api.get('/api/courses/1').get_json()['course']['name'] == 'Curso geral'


def test_student_cannot_rename_or_write_questions(student_api, admin_api):
    assert student_api.put('/api/courses/1', {'name': 'Outro'}).status_code == 403
    assert student_api.post('/api/courses/1/questions', {'new_prompt': 'Outra'}).status_code == 403
    question = add_question(admin_api)
    denied = admin_api.post('/api/courses/1/answers', {'answers': [{'id': question['id'], 'answer': 'Lisboa'}]})
    assert denied.status_code == 403


def test_prompt_edit_keeps_the_answer_and_removal_drops_it(admin_api, student_api):
    question = add_question(admin_api)
    saved = student_api.post('/api/courses/1/answers', {'answers': [{'id': question['id'], 'answer': 'Lisboa'}]})
    assert saved.get_json()['course']['questions'][0]['answer'] == 'Lisboa'

    edited = admin_api.post('/api/courses/1/questions', {
        'questions': [{'id': question['id'], 'prompt': 'Capital de Portugal?'}],
        'new_prompt': '',
    })
    kept = edited.get_json()['course']['questions'][0]
    assert kept['prompt'] == 'Capital de Portugal?'
    assert kept['answer'] == 'Lisboa'

    blank = admin_api.post('/api/courses/1/questions', {
        'questions': [{'id': question['id'], 'prompt': '  '}],
        'new_prompt': '',
    })
    assert blank.status_code == 400
    assert blank.get_json()['error'] == 'O texto da pergunta é obrigatório.'

    removed = admin_api.post('/api/courses/1/questions', {
        'questions': [{'id': question['id'], 'remove': True}],
        'new_prompt': '   ',
    })
    assert removed.get_json()['course']['questions'] == []


def test_course_completes_only_when_lessons_and_answers_are_done(admin_api, student_api):
    question = add_question(admin_api)
    student_api.post('/api/courses/1/lessons/1/complete')
    unfinished = student_api.get('/api/courses/1').get_json()['course']
    assert unfinished['completed_at'] is None

    answered = student_api.post('/api/courses/1/answers', {
        'answers': [{'id': question['id'], 'answer': 'Lisboa'}],
    })
    completed_at = answered.get_json()['course']['completed_at']
    assert completed_at.endswith('Z')

    cleared = student_api.post('/api/courses/1/answers', {
        'answers': [{'id': question['id'], 'answer': '  '}],
    })
    assert cleared.get_json()['course']['completed_at'] == completed_at


def test_new_lesson_keeps_completion(admin_api, student_api):
    student_api.post('/api/courses/1/lessons/1/complete')
    completed_at = student_api.get('/api/courses/1').get_json()['course']['completed_at']
    assert completed_at is not None

    created = admin_api.post('/api/courses/1/lessons', VALID_LESSON)

    assert created.status_code == 201
    assert student_api.get('/api/courses/1').get_json()['course']['completed_at'] == completed_at


def test_next_course_opens_on_the_following_sao_paulo_day(admin_api, student_api):
    second = admin_api.post('/api/courses', {'name': 'História'}).get_json()['course']
    lesson = admin_api.post(f"/api/courses/{second['id']}/lessons", VALID_LESSON).get_json()['lesson']

    locked = student_api.get('/api/courses').get_json()['courses'][1]
    assert locked['is_available'] is False
    assert locked['unavailable_reason'] == 'Disponível depois de concluir o curso anterior'
    denied = student_api.get(f"/api/courses/{second['id']}")
    assert denied.status_code == 403
    assert denied.get_json()['error'] == 'Disponível depois de concluir o curso anterior'
    lesson_path = f"/api/courses/{second['id']}/lessons/{lesson['id']}"
    assert student_api.get(lesson_path).status_code == 403
    assert student_api.post(f'{lesson_path}/complete').status_code == 403

    admin_row = admin_api.get('/api/courses').get_json()['courses'][1]
    assert admin_row['is_available'] is True
    assert admin_row['unavailable_reason'] is None
    assert admin_api.get(f"/api/courses/{second['id']}").status_code == 200

    student_api.post('/api/courses/1/lessons/1/complete')
    waiting = student_api.get('/api/courses').get_json()['courses'][1]
    assert waiting['is_available'] is False
    assert waiting['unavailable_reason'].startswith('Disponível em ')

    course = db.session.get(Course, 1)
    course.completed_at = course.completed_at - timedelta(days=2)
    db.session.commit()

    opened = student_api.get('/api/courses').get_json()['courses'][1]
    assert opened['is_available'] is True
    assert opened['unavailable_reason'] is None


def test_empty_course_never_meets_requirements():
    course = SimpleNamespace(lessons=[], questions=[], completed_at=None)
    assert course_requirements_met(course) is False


def test_late_evening_in_sao_paulo_unlocks_the_next_local_day():
    completed_at = datetime(2026, 10, 26, 21, 0, tzinfo=ZoneInfo('America/Sao_Paulo'))
    stored = completed_at.astimezone(timezone.utc).replace(tzinfo=None)
    previous = SimpleNamespace(completed_at=stored)

    same_day_open, same_day_reason = course_availability(previous, date(2026, 10, 26))
    next_day_open, next_day_reason = course_availability(previous, date(2026, 10, 27))

    assert same_day_open is False
    assert same_day_reason == 'Disponível em 27/10/2026'
    assert next_day_open is True
    assert next_day_reason is None
