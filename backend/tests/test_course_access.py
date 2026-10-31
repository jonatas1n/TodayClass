from datetime import timedelta

import pytest

from todayclass.models import Course, Lesson, db, naive_utc_now

WAITING_FOR_PREVIOUS_COURSE = 'Disponível depois de concluir o curso anterior'
EXTRA_LESSON = {'day': '2', 'title': 'Aula extra', 'content': '<p>Mais</p>', 'links': []}


@pytest.fixture(autouse=True)
def empty_catalog(app):
    for course in Course.query.all():
        db.session.delete(course)
    db.session.commit()


def add_course(name, lesson_count=1, completed_days_ago=None):
    course = Course(name=name)
    completed_at = None
    if completed_days_ago is not None:
        completed_at = naive_utc_now() - timedelta(days=completed_days_ago)
    for day in range(1, lesson_count + 1):
        course.lessons.append(Lesson(
            day=day,
            title=f'Aula {day}',
            content='<p>Conteúdo</p>',
            is_completed=completed_at is not None,
            completed_at=completed_at,
        ))
    course.completed_at = completed_at
    db.session.add(course)
    db.session.commit()
    return course.id


def course_status(client, course_id):
    return client.get(f'/api/courses/{course_id}').status_code


def listed_reasons(client):
    return [course['unavailable_reason'] for course in client.get('/api/courses').get_json()['courses']]


def test_first_course_is_open_for_student(student_api):
    first_course_id = add_course('Português')

    assert course_status(student_api, first_course_id) == 200


def test_next_course_is_locked_until_previous_is_completed(student_api):
    add_course('Português')
    second_course_id = add_course('História')

    assert course_status(student_api, second_course_id) == 403
    assert WAITING_FOR_PREVIOUS_COURSE in listed_reasons(student_api)


def test_next_course_stays_locked_on_the_completion_day(student_api):
    add_course('Português', completed_days_ago=0)
    second_course_id = add_course('História')

    assert course_status(student_api, second_course_id) == 403


def test_next_course_opens_the_day_after_completion(student_api):
    add_course('Português', completed_days_ago=2)
    second_course_id = add_course('História')

    assert course_status(student_api, second_course_id) == 200


def test_empty_course_does_not_block_later_courses(student_api):
    add_course('Português', completed_days_ago=2)
    add_course('História', lesson_count=0)
    third_course_id = add_course('Geografia')

    assert course_status(student_api, third_course_id) == 200
    assert WAITING_FOR_PREVIOUS_COURSE not in listed_reasons(student_api)


def test_adding_a_lesson_to_completed_course_keeps_next_course_open(student_api, admin_api):
    first_course_id = add_course('Português', completed_days_ago=2)
    second_course_id = add_course('História')

    response = admin_api.post(f'/api/courses/{first_course_id}/lessons', EXTRA_LESSON)

    assert response.status_code == 201
    assert course_status(student_api, second_course_id) == 200


def test_adding_a_question_to_completed_course_keeps_next_course_open(student_api, admin_api):
    first_course_id = add_course('Português', completed_days_ago=2)
    second_course_id = add_course('História')

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
