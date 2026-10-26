from todayclass.models import Lesson, db

VALID_LESSON = {
    'day': '2',
    'title': 'Aula 2',
    'content': '<p>Conteúdo</p>',
    'links': [{'title': 'Leitura', 'url': 'https://example.com/leitura'}],
}


def test_anonymous_user_cannot_list_courses(api):
    assert api.get('/api/courses').status_code == 401


def test_student_lists_courses_with_lesson_counts(student_api):
    payload = student_api.get('/api/courses').get_json()

    assert payload['courses'] == [{'id': 1, 'name': 'Curso geral', 'lesson_count': 1}]


def test_student_cannot_create_course(student_api):
    assert student_api.post('/api/courses', {'name': 'Novo'}).status_code == 403


def test_admin_creates_course(admin_api):
    response = admin_api.post('/api/courses', {'name': '  Violão  '})

    assert response.status_code == 201
    assert response.get_json()['course']['name'] == 'Violão'


def test_course_name_is_required(admin_api):
    response = admin_api.post('/api/courses', {'name': '   '})

    assert response.status_code == 400
    assert response.get_json()['error'] == 'O nome é obrigatório.'


def test_admin_creates_lesson_with_links(admin_api):
    response = admin_api.post('/api/courses/1/lessons', VALID_LESSON)

    lesson = response.get_json()['lesson']
    assert response.status_code == 201
    assert lesson['label'] == 'Dia 2 - Aula 2'
    assert lesson['links'] == [{'id': lesson['links'][0]['id'], 'title': 'Leitura', 'url': 'https://example.com/leitura'}]


def test_lesson_day_must_be_in_range(admin_api):
    response = admin_api.post('/api/courses/1/lessons', {**VALID_LESSON, 'day': '0'})

    assert response.status_code == 400
    assert response.get_json()['error'] == 'O dia deve ser um número inteiro de 1 a 9999.'


def test_lesson_link_needs_http_url(admin_api):
    links = [{'title': 'Leitura', 'url': 'ftp://example.com'}]

    response = admin_api.post('/api/courses/1/lessons', {**VALID_LESSON, 'links': links})

    assert response.status_code == 400
    assert response.get_json()['error'] == 'A URL do link deve começar com http:// ou https://.'


def test_blank_link_rows_are_ignored(admin_api):
    links = [{'title': '', 'url': ''}, {'title': 'Leitura', 'url': 'https://example.com'}]

    response = admin_api.post('/api/courses/1/lessons', {**VALID_LESSON, 'links': links})

    assert [link['title'] for link in response.get_json()['lesson']['links']] == ['Leitura']


def test_missing_lesson_returns_not_found(student_api):
    response = student_api.get('/api/courses/1/lessons/999')

    assert response.status_code == 404
    assert response.get_json()['error'] == 'Não encontrado.'


def test_editing_lesson_keeps_completion_and_replaces_links(admin_api):
    lesson = db.session.get(Lesson, 1)
    lesson.is_completed = True
    db.session.commit()
    completed_at = admin_api.get('/api/courses/1/lessons/1').get_json()['lesson']['completed_at']

    response = admin_api.put('/api/courses/1/lessons/1', {**VALID_LESSON, 'title': 'Revista'})

    edited = response.get_json()['lesson']
    assert response.status_code == 200
    assert edited['title'] == 'Revista'
    assert edited['is_completed'] is True
    assert edited['completed_at'] == completed_at
    assert [link['title'] for link in edited['links']] == ['Leitura']


def test_invalid_edit_leaves_lesson_unchanged(admin_api):
    response = admin_api.put('/api/courses/1/lessons/1', {**VALID_LESSON, 'title': ''})

    assert response.status_code == 400
    assert admin_api.get('/api/courses/1/lessons/1').get_json()['lesson']['title'] == 'Aula 1'


def test_student_cannot_edit_lesson(student_api):
    assert student_api.put('/api/courses/1/lessons/1', VALID_LESSON).status_code == 403


def test_student_completes_lesson(student_api):
    response = student_api.post('/api/courses/1/lessons/1/complete')

    lesson = response.get_json()['lesson']
    assert response.status_code == 200
    assert lesson['is_completed'] is True
    assert lesson['completed_at'].endswith('Z')


def test_completing_twice_keeps_first_completion_time(student_api):
    first = student_api.post('/api/courses/1/lessons/1/complete').get_json()['lesson']
    second = student_api.post('/api/courses/1/lessons/1/complete').get_json()['lesson']

    assert second['completed_at'] == first['completed_at']


def test_admin_cannot_complete_lesson(admin_api):
    assert admin_api.post('/api/courses/1/lessons/1/complete').status_code == 403
