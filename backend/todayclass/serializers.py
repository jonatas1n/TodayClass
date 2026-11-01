from .schedule import completed_on


def utc_timestamp(value):
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + 'Z'


def user_payload(user):
    return {'id': user.id, 'username': user.username, 'role': user.role}


def link_payload(link):
    return {'id': link.id, 'title': link.title, 'url': link.url}


def lesson_summary_payload(lesson, is_available=True, unavailable_reason=None):
    return {
        'id': lesson.id,
        'course_id': lesson.course_id,
        'day': lesson.day,
        'title': lesson.title,
        'label': lesson.label,
        'is_completed': lesson.is_completed,
        'completed_at': utc_timestamp(lesson.completed_at),
        'is_available': is_available,
        'unavailable_reason': unavailable_reason,
    }


def lesson_payload(lesson):
    payload = lesson_summary_payload(lesson)
    payload['content'] = lesson.content
    payload['course_name'] = lesson.course.name
    payload['links'] = [link_payload(link) for link in lesson.links]
    return payload


def progress_row_payload(lesson):
    payload = lesson_summary_payload(lesson)
    payload['course_name'] = lesson.course.name
    payload['link_count'] = len(lesson.links)
    return payload


def question_payload(question):
    return {
        'id': question.id,
        'position': question.position,
        'prompt': question.prompt,
        'answer': question.answer or '',
    }


def course_summary_payload(course, lesson_count):
    return {
        'id': course.id,
        'name': course.name,
        'lesson_count': lesson_count,
        'completed_at': utc_timestamp(course.completed_at),
        'completed_on': completed_on(course),
        'is_available': True,
        'unavailable_reason': None,
    }


def course_payload(course, lesson_availability=None):
    lesson_availability = lesson_availability or {}
    lessons = []
    for lesson in course.lessons:
        is_available, reason = lesson_availability.get(lesson.id, (True, None))
        lessons.append(lesson_summary_payload(lesson, is_available, reason))
    return {
        'id': course.id,
        'name': course.name,
        'completed_at': utc_timestamp(course.completed_at),
        'completed_on': completed_on(course),
        'lessons': lessons,
        'questions': [question_payload(question) for question in course.questions],
    }
