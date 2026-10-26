def utc_timestamp(value):
    if value is None:
        return None
    return value.replace(microsecond=0).isoformat() + 'Z'


def user_payload(user):
    return {'id': user.id, 'username': user.username, 'role': user.role}


def link_payload(link):
    return {'id': link.id, 'title': link.title, 'url': link.url}


def lesson_summary_payload(lesson):
    return {
        'id': lesson.id,
        'course_id': lesson.course_id,
        'day': lesson.day,
        'title': lesson.title,
        'label': lesson.label,
        'is_completed': lesson.is_completed,
        'completed_at': utc_timestamp(lesson.completed_at),
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


def course_summary_payload(course, lesson_count):
    return {'id': course.id, 'name': course.name, 'lesson_count': lesson_count}


def course_payload(course):
    return {
        'id': course.id,
        'name': course.name,
        'lessons': [lesson_summary_payload(lesson) for lesson in course.lessons],
    }
