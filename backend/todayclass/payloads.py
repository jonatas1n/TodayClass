from flask import abort, request


def json_body():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(400, description='Envie os dados como JSON.')
    return payload


def form_text(payload, key):
    value = payload.get(key, '')
    if not isinstance(value, str):
        return ''
    return value.strip()


def form_password(payload, key='password'):
    value = payload.get(key, '')
    if not isinstance(value, str):
        return ''
    return value
