from conftest import CSRF_TOKEN, add_course, course_completed_at, first_lesson_id

WAITING_FOR_PREVIOUS_COURSE = 'Disponível depois de concluir o curso anterior'


def course_page_status(client, course_id):
    return client.get(f'/courses/{course_id}').status_code


def course_list_text(client):
    return client.get('/courses').get_data(as_text=True)


def test_first_course_is_open_for_student(application, student_client):
    first_course_id = add_course(application, 'Português')

    assert course_page_status(student_client, first_course_id) == 200


def test_next_course_is_locked_until_previous_is_completed(application, student_client):
    add_course(application, 'Português')
    second_course_id = add_course(application, 'História')

    assert course_page_status(student_client, second_course_id) == 302
    assert WAITING_FOR_PREVIOUS_COURSE in course_list_text(student_client)


def test_next_course_stays_locked_on_the_completion_day(application, student_client):
    add_course(application, 'Português', completed_days_ago=0)
    second_course_id = add_course(application, 'História')

    assert course_page_status(student_client, second_course_id) == 302


def test_next_course_opens_the_day_after_completion(application, student_client):
    add_course(application, 'Português', completed_days_ago=2)
    second_course_id = add_course(application, 'História')

    assert course_page_status(student_client, second_course_id) == 200


def test_empty_course_does_not_block_later_courses(application, student_client):
    add_course(application, 'Português', completed_days_ago=2)
    add_course(application, 'História', lesson_count=0)
    third_course_id = add_course(application, 'Geografia')

    assert course_page_status(student_client, third_course_id) == 200
    assert WAITING_FOR_PREVIOUS_COURSE not in course_list_text(student_client)


def test_adding_a_lesson_to_completed_course_keeps_next_course_open(application, student_client, admin_client):
    first_course_id = add_course(application, 'Português', completed_days_ago=2)
    second_course_id = add_course(application, 'História')

    response = admin_client.post(
        f'/courses/{first_course_id}/lessons/new',
        data={'csrf_token': CSRF_TOKEN, 'day': '2', 'title': 'Aula extra', 'content': '<p>Mais</p>'},
    )

    assert response.status_code == 302
    assert course_page_status(student_client, second_course_id) == 200


def test_adding_a_question_to_completed_course_keeps_next_course_open(application, student_client, admin_client):
    first_course_id = add_course(application, 'Português', completed_days_ago=2)
    second_course_id = add_course(application, 'História')

    response = admin_client.post(
        f'/courses/{first_course_id}/questions',
        data={'csrf_token': CSRF_TOKEN, 'new_prompt': 'Qual é a capital?'},
    )

    assert response.status_code == 302
    assert course_page_status(student_client, second_course_id) == 200


def test_student_completing_last_lesson_completes_course(application, student_client):
    first_course_id = add_course(application, 'Português')
    lesson_id = first_lesson_id(application, first_course_id)

    student_client.post(f'/courses/{first_course_id}/lessons/{lesson_id}', data={'csrf_token': CSRF_TOKEN})

    assert course_completed_at(application, first_course_id) is not None


def test_admin_sees_every_course_open(application, admin_client):
    add_course(application, 'Português')
    second_course_id = add_course(application, 'História')

    assert course_page_status(admin_client, second_course_id) == 200
