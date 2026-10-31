from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo('America/Sao_Paulo')
PREVIOUS_COURSE_REASON = 'Disponível depois de concluir o curso anterior'


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


def course_requirements_met(course):
    if not course.lessons and not course.questions:
        return False
    if not lessons_are_finished(course):
        return False
    return questions_are_answered(course)


def apply_completion_state(course, moment):
    if course_requirements_met(course):
        if course.completed_at is not None:
            return False
        course.completed_at = moment
        return True
    if course.completed_at is None:
        return False
    course.completed_at = None
    return True


def completed_on(course):
    if course.completed_at is None:
        return None
    return sao_paulo_date(course.completed_at).isoformat()


def course_availability(previous_course, today):
    if previous_course is None:
        return True, None
    if previous_course.completed_at is None:
        return False, PREVIOUS_COURSE_REASON
    unlock_on = sao_paulo_date(previous_course.completed_at) + timedelta(days=1)
    if today >= unlock_on:
        return True, None
    return False, f'Disponível em {unlock_on.strftime("%d/%m/%Y")}'
