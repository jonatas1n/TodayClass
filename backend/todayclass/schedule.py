from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo('America/Sao_Paulo')
PREVIOUS_LESSON_REASON = 'Disponível depois de concluir a aula anterior'


def as_utc(moment):
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def sao_paulo_date(moment):
    return as_utc(moment).astimezone(SAO_PAULO).date()


def lessons_are_finished(course):
    return all(lesson.is_completed for lesson in course.lessons)


def questions_are_answered(course):
    return all((question.answer or '').strip() for question in course.questions)


def course_has_content(course):
    return bool(course.lessons or course.questions)


def course_requirements_met(course):
    if not course_has_content(course):
        return False
    if not lessons_are_finished(course):
        return False
    return questions_are_answered(course)


def apply_completion_state(course, moment):
    # Completion stays once earned, even if a lesson or question is added later.
    if course.completed_at is not None:
        return False
    if not course_requirements_met(course):
        return False
    course.completed_at = moment
    return True


def completed_on(course):
    if course.completed_at is None:
        return None
    return sao_paulo_date(course.completed_at).isoformat()


def lesson_availability(previous_lesson, today):
    if previous_lesson is None:
        return True, None
    if previous_lesson.completed_at is None:
        return False, PREVIOUS_LESSON_REASON
    unlock_on = sao_paulo_date(previous_lesson.completed_at) + timedelta(days=1)
    if today >= unlock_on:
        return True, None
    return False, f'Disponível em {unlock_on.strftime("%d/%m/%Y")}'


def availability_by_lesson_id(lessons, today):
    availability = {}
    previous_lesson = None
    for lesson in lessons:
        if lesson.is_completed:
            availability[lesson.id] = (True, None)
            previous_lesson = lesson
            continue
        availability[lesson.id] = lesson_availability(previous_lesson, today)
        previous_lesson = lesson
    return availability
