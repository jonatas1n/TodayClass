# TodayClass

Um curso por dia, no celular. Você escreve a aula, seu pai lê e marca como feita.

O sistema tem três partes, cada uma num serviço com plano gratuito:

| Parte | Pasta | Onde roda |
| --- | --- | --- |
| Frontend (HTML, CSS e JS puros) | [`frontend/`](frontend) | [Cloudflare Pages](https://pages.cloudflare.com/) |
| API Flask em JSON | [`backend/`](backend) | [Vercel](https://vercel.com/), como função serverless |
| Banco SQLite | | [Turso](https://turso.tech/) |

O navegador só conversa com o domínio do Pages. Uma Pages Function em [`frontend/functions/api/[[path]].js`](frontend/functions/api/[[path]].js) repassa todo `/api/*` para a Vercel. Assim o cookie de sessão continua sendo do mesmo site, e não é preciso configurar CORS.

## Estrutura

```
backend/
  api/index.py          entrada da função na Vercel
  todayclass/           app Flask (create_app, modelos, validação, rotas)
  scripts/init_db.py    cria as tabelas e a aula de exemplo
  tests/                testes com pytest
  dev.py                servidor local que também serve o frontend
frontend/
  public/               páginas, CSS, JS e marca
  functions/api/        proxy de /api para a Vercel
  tests/                testes do proxy com node --test
```

## Rotas da API

| Rota | Quem acessa | O que faz |
| --- | --- | --- |
| `GET /api/session` | todos | usuário atual, `needs_setup` e o token CSRF |
| `POST /api/setup` | ninguém, só na primeira vez | cria a conta de admin |
| `POST /api/login`, `POST /api/logout` | todos | entra e sai |
| `GET /api/courses`, `GET /api/courses/<id>` | aluno ou admin | lista os cursos e as aulas de um curso |
| `POST /api/courses` | admin | cria um curso |
| `GET /api/courses/<id>/lessons/<id>` | aluno ou admin | lê uma aula |
| `POST`/`PUT` em `/api/courses/<id>/lessons[/<id>]` | admin | cria ou edita uma aula |
| `POST /api/courses/<id>/lessons/<id>/complete` | aluno | marca a aula como feita |
| `/api/admin/progress`, `/api/admin/users` | admin | progresso, logins e troca de senha |

Todo `POST`, `PUT`, `PATCH` e `DELETE` precisa de corpo JSON e do cabeçalho `X-CSRF-Token` com o token de `/api/session`. O `frontend/public/js/api.js` cuida disso.

O conteúdo da aula é HTML e é renderizado de propósito. Escreva o texto você mesmo e não cole HTML de outra pessoa.

## Rodar na sua máquina

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
python dev.py
```

Abra [http://localhost:5001/setup.html](http://localhost:5001/setup.html), crie o admin e, no painel de progresso, crie o login do seu pai. A senha precisa ter pelo menos 8 caracteres. A porta é 5001 porque, no macOS, a 5000 costuma estar ocupada pelo AirPlay.

Sem `TURSO_DATABASE_URL`, o backend usa o arquivo `backend/courses.db`. Se ainda não houver nenhuma aula, ele cria o Dia 1 para você ver o formato.

Testes:

```bash
cd backend && pytest
cd frontend && npm test
```

## Banco no Turso

Com a [CLI do Turso](https://docs.turso.tech/cli/introduction) instalada e logada:

```bash
# Para levar um courses.db que já existe (por exemplo, o do PythonAnywhere):
turso db create todayclass --from-file courses.db

# Ou, para começar do zero:
turso db create todayclass

turso db show todayclass --url    # libsql://todayclass-<usuario>.turso.io
turso db tokens create todayclass
```

Se o banco foi criado do zero, crie as tabelas e a aula de exemplo uma vez:

```bash
cd backend
TURSO_DATABASE_URL=libsql://... TURSO_AUTH_TOKEN=... SECRET_KEY=qualquer python scripts/init_db.py
```

## Publicar o backend na Vercel

1. Importe o repositório na Vercel e defina **Root Directory** como `backend`.
2. Em Environment Variables, defina:
   - `SECRET_KEY`: um valor longo e aleatório (`python -c "import secrets; print(secrets.token_hex(32))"`).
   - `TURSO_DATABASE_URL`: a URL `libsql://...` do passo anterior.
   - `TURSO_AUTH_TOKEN`: o token criado.
3. Publique e anote o domínio, por exemplo `https://todayclass-api.vercel.app`.

O [`backend/vercel.json`](backend/vercel.json) manda toda requisição para `api/index.py`. Sem `SECRET_KEY`, a função falha logo ao iniciar, de propósito.

## Publicar o frontend no Cloudflare Pages

1. Crie um projeto no Pages ligado ao repositório.
2. Defina **Root directory** como `frontend`, deixe o build command vazio e use `public` como **Build output directory**.
3. Em Environment Variables, defina `API_ORIGIN` com o domínio da Vercel (`https://todayclass-api.vercel.app`).
4. Publique e visite `/setup.html` no domínio do Pages.

Para testar o Pages localmente com o proxy, rode `npx wrangler pages dev` dentro de `frontend/`, com `API_ORIGIN` definido em `frontend/.dev.vars`.

## Contas

Há dois papéis, `admin` e `student`, na tabela `User`. A senha é gravada com hash. Não existe cadastro público: depois do primeiro admin, `/api/setup` responde 404. Se alguém esquecer a senha, o admin define outra no painel.

O cookie de sessão é `Secure`, `HttpOnly` e `SameSite=Lax`. O progresso é do curso, não de cada pessoa: um aluno, um dia, uma conclusão.
