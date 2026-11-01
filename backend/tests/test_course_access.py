import pytest

from todayclass.models import Course, Lesson, db

EXTRA_LESSON = {'day': '2', 'title': 'Aula extra', 'content': '<p>Mais</p>', 'links': []}


@pytest.fixture(autouse=True)
def empty_catalog(app):
    for course in Course.query.all():
        db.session.delete(course)
    db.session.commit()


def add_course(name, lesson_count=1):
    course = Course(name=name)
    for day in range(1, lesson_count + 1):
        course.lessons.append(Lesson(
            day=day,
            title=f'Aula {day}',
            content='<p>Conteúdo</p>',
            is_completed=False,
            completed_at=None,
        ))
    db.session.add(course)
    db.session.commit()
    return course.id


def course_status(client, course_id):
    return client.get(f'/api/courses/{course_id}').status_code


def test_student_can_open_another_course_after_an_unfinished_course(student_api):
    add_course('Português')
    history_course_id = add_course('História')

    courses = student_api.get('/api/courses').get_json()['courses']

    assert course_status(student_api, history_course_id) == 200
    assert courses[1]['is_available'] is True
    assert courses[1]['unavailable_reason'] is None


def test_empty_course_does_not_block_a_later_course_on_the_same_day(student_api):
    add_course('Português')
    add_course('História', lesson_count=0)
    geography_course_id = add_course('Geografia')

    courses = student_api.get('/api/courses').get_json()['courses']

    assert course_status(student_api, geography_course_id) == 200
    assert courses[2]['is_available'] is True
    assert courses[2]['unavailable_reason'] is None


def test_adding_a_lesson_to_completed_course_keeps_next_course_open(student_api, admin_api):
    first_course_id = add_course('Português')
    second_course_id = add_course('História')
    first_lesson_id = db.session.get(Course, first_course_id).lessons[0].id
    student_api.post(f'/api/courses/{first_course_id}/lessons/{first_lesson_id}/complete')

    response = admin_api.post(f'/api/courses/{first_course_id}/lessons', EXTRA_LESSON)

    assert response.status_code == 201
    assert course_status(student_api, second_course_id) == 200


def test_adding_a_question_to_completed_course_keeps_next_course_open(student_api, admin_api):
    first_course_id = add_course('Português')
    second_course_id = add_course('História')
    first_lesson_id = db.session.get(Course, first_course_id).lessons[0].id
    student_api.post(f'/api/courses/{first_course_id}/lessons/{first_lesson_id}/complete')

    response = admin_api.post(
        f'/api/courses/{first_course_id}/questions',
        {'questions': [], 'new_prompt': 'Qual é a capital?'},
    )

    assert response.status_code == 200
    assert course_status(student_api, second_course_id) == 200


def test_student_completing_last_lesson_completes_course(student_api):
    first_course_id = add_course('Português')
    lesson_id = db.session.get(Course, first_course_id).lessons[0].id

    student_api.post(f'/api/courses/{first_course_id}/lessons/{lesson_id}/complete')

    assert student_api.get(f'/api/courses/{first_course_id}').get_json()['course']['completed_at'] is not None


def test_admin_sees_every_course_open(admin_api):
    add_course('Português')
    second_course_id = add_course('História')

    assert course_status(admin_api, second_course_id) == 200
