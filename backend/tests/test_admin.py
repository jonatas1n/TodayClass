def test_student_cannot_read_progress(student_api):
    assert student_api.get('/api/admin/progress').status_code == 403


def test_admin_reads_progress_rows(admin_api):
    rows = admin_api.get('/api/admin/progress').get_json()['lessons']

    assert rows[0]['course_name'] == 'Curso geral'
    assert rows[0]['label'] == 'Dia 1 - Aula 1'
    assert rows[0]['link_count'] == 1


def test_admin_creates_student_login(admin_api):
    response = admin_api.post(
        '/api/admin/users',
        {'username': 'pai', 'password': 'senha-segura', 'role': 'student'},
    )

    assert response.status_code == 201
    usernames = [user['username'] for user in admin_api.get('/api/admin/users').get_json()['users']]
    assert usernames == ['admin', 'pai']


def test_duplicate_username_is_rejected(admin_api):
    response = admin_api.post(
        '/api/admin/users',
        {'username': 'admin', 'password': 'senha-segura', 'role': 'admin'},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'Esse usuário já está em uso.'


def test_invalid_role_is_rejected(admin_api):
    response = admin_api.post(
        '/api/admin/users',
        {'username': 'pai', 'password': 'senha-segura', 'role': 'dono'},
    )

    assert response.get_json()['error'] == 'Escolha um papel válido.'


def test_admin_resets_password_and_new_password_works(admin_api, api):
    response = admin_api.put('/api/admin/users/1/password', {'password': 'nova-senha-1'})

    assert response.status_code == 200
    assert api.login('admin', 'nova-senha-1').status_code == 200
