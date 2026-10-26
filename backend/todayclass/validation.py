STUDENT_ROLE = 'student'
ADMIN_ROLE = 'admin'
ROLES = (STUDENT_ROLE, ADMIN_ROLE)
MINIMUM_PASSWORD_LENGTH = 8
MAXIMUM_USERNAME_LENGTH = 80
MAXIMUM_COURSE_NAME_LENGTH = 120
MAXIMUM_LESSON_TITLE_LENGTH = 120
MAXIMUM_DAY_NUMBER = 9999
MAXIMUM_LINK_TITLE_LENGTH = 100
MAXIMUM_LINK_URL_LENGTH = 255
MAXIMUM_LINK_COUNT = 4


def username_validation_error(username):
    if not username:
        return 'O usuário é obrigatório.'
    if len(username) > MAXIMUM_USERNAME_LENGTH:
        return 'O usuário é longo demais.'
    return None


def password_validation_error(password):
    if not password:
        return 'A senha é obrigatória.'
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        return f'A senha deve ter pelo menos {MINIMUM_PASSWORD_LENGTH} caracteres.'
    return None


def account_validation_error(username, password, role):
    username_error = username_validation_error(username)
    if username_error:
        return username_error
    password_error = password_validation_error(password)
    if password_error:
        return password_error
    if role not in ROLES:
        return 'Escolha um papel válido.'
    return None


def required_text_error(field_label, value, maximum_length):
    if not value:
        return f'{field_label} é obrigatório.'
    if len(value) > maximum_length:
        return f'{field_label} é longo demais.'
    return None


def parse_day_number(raw_value):
    stripped_value = str(raw_value).strip()
    if not stripped_value.isdecimal():
        return None
    day_number = int(stripped_value)
    if day_number < 1 or day_number > MAXIMUM_DAY_NUMBER:
        return None
    return day_number


def text_value(value):
    if not isinstance(value, str):
        return ''
    return value.strip()


def completed_link_pairs(raw_links):
    if not isinstance(raw_links, list):
        return []
    pairs = []
    for raw_link in raw_links:
        if not isinstance(raw_link, dict):
            continue
        title = text_value(raw_link.get('title'))
        url = text_value(raw_link.get('url'))
        if not title and not url:
            continue
        pairs.append((title, url))
    return pairs


def is_http_url(url):
    return url.startswith(('http://', 'https://'))


def link_error(title, url):
    if not title or not url:
        return 'Cada link precisa de um título e uma URL.'
    if len(title) > MAXIMUM_LINK_TITLE_LENGTH:
        return 'O título do link é longo demais.'
    if len(url) > MAXIMUM_LINK_URL_LENGTH:
        return 'A URL do link é longa demais.'
    if not is_http_url(url):
        return 'A URL do link deve começar com http:// ou https://.'
    return None


def link_pairs_error(pairs):
    if len(pairs) > MAXIMUM_LINK_COUNT:
        return f'Uma aula pode ter no máximo {MAXIMUM_LINK_COUNT} links.'
    for title, url in pairs:
        error = link_error(title, url)
        if error:
            return error
    return None


def lesson_form_error(day_number, title, content, pairs):
    if day_number is None:
        return f'O dia deve ser um número inteiro de 1 a {MAXIMUM_DAY_NUMBER}.'
    title_error = required_text_error('O título', title, MAXIMUM_LESSON_TITLE_LENGTH)
    if title_error:
        return title_error
    if not content.strip():
        return 'O conteúdo é obrigatório.'
    return link_pairs_error(pairs)
