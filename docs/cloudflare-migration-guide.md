# Guia de migração para a Cloudflare (frontend + backend)

> **RASCUNHO, segunda versão (31/10/2026).** Ainda não foi revisado nem testado. As versões de pacotes foram consultadas no npm nesta data, mas a documentação da Cloudflare **não** foi lida durante a escrita. Tudo marcado com **[verificar]** precisa ser confirmado na documentação oficial antes de executar.

## Decisões já tomadas

| Tema | Decisão |
| --- | --- |
| Frontend | Manter o HTML/CSS/JS estático de `feat/migration` (`frontend/public`). Next.js **não** faz parte do plano (ver apêndice). |
| Produção hoje | `main` no PythonAnywhere, com o SQLite em arquivo (`courses.db`). O branch `feat/migration` (Vercel + Turso + Pages) **não** está no ar. Ele é a referência do schema e do contrato da API. |
| Banco | Ficar no **Turso**. O `courses.db` do PythonAnywhere é importado para lá. D1 fica como passo posterior opcional, sem data. |
| Plano do Workers | **Free.** |
| Senhas | Reset no dia da troca. O Worker **não** verifica os hashes scrypt do Werkzeug. Senhas novas usam PBKDF2 via WebCrypto. |
| Sessão | Cookie novo, assinado no Worker. Todo mundo entra de novo depois da troca. Isso é aceitável. |

---

## 0. O que este guia cobre

O pedido original falava em Next.js. Não há Next.js nem React em nenhum dos worktrees (o commit `3a4db6f` diz "react", mas o frontend é HTML e JS puros). O plano é:

1. Servir `frontend/public` como Static Assets de um Worker.
2. Reescrever a API Flask de `feat/migration` em TypeScript (Hono), no mesmo Worker, em `/api/*`.
3. Levar o `courses.db` do PythonAnywhere para o Turso, no schema desse branch.

---

## 1. Arquitetura atual

### 1.1 `main` (produção, PythonAnywhere)

| Peça | Implementação |
| --- | --- |
| App | Flask 3 + Flask-Login + Flask-SQLAlchemy, tudo em `app.py` |
| Páginas | Jinja (`templates/*.html`), renderização no servidor |
| Banco | SQLite em arquivo (`courses.db` ao lado do `app.py`), no disco do PythonAnywhere |
| Sessão | Cookie assinado do Flask (`SECRET_KEY`), `Secure`, `HttpOnly`, `SameSite=Lax` |
| CSRF | Token na sessão, validado nos formulários |
| Senhas | `werkzeug.security.generate_password_hash`. No `courses.db` local, o formato é `scrypt:32768:8:1$<salt>$<hex>`. Esses hashes **não** serão usados no Worker |
| Arquivos | Só estáticos (`static/css`, `static/js`, `static/brand`). **Não há upload nem vídeo.** As aulas são HTML no banco, mais links externos |

O `app.py` ainda sabe migrar um schema antigo na subida (`prepare_database`): se `course` tiver a coluna `day`, a tabela é aula, não curso. Isso importa na seção 4.2, porque o arquivo no PythonAnywhere pode estar nesse formato ou já no formato novo.

### 1.2 `feat/migration` (referência, não está em produção)

| Peça | Como está no branch | No plano |
| --- | --- | --- |
| Frontend estático | `frontend/public/`, sem build | **Entra.** Vira Static Assets do Worker |
| Proxy `/api/*` | `frontend/functions/api/[[path]].js` (Pages Function → Vercel) | **Não entra.** A API mora no mesmo Worker |
| API Flask JSON | `backend/todayclass/`, `backend/vercel.json` | **Contrato a portar** para Hono. A Vercel não é um passo da migração |
| Banco | Turso via `sqlalchemy-libsql` (`backend/todayclass/config.py`) | **Destino dos dados**, alimentado pelo `courses.db` de produção |
| Testes | pytest + `node --test` | Os pytest são a especificação a portar |

Diferenças de comportamento em relação ao `main`:

- Páginas Jinja viraram HTML que chama `/api/*` (`frontend/public/js/api.js`). O CSRF vai no header `X-CSRF-Token`, devolvido por `GET /api/session`.
- Todo `POST/PUT/PATCH/DELETE` exige corpo JSON (`validate_csrf` em `auth.py`).
- O schema é criado com `db.create_all()` (`scripts/init_db.py`). **Não há ferramenta de migração de schema.**
- O desbloqueio de cursos segue o calendário de São Paulo (`schedule.py`), e a conclusão é recalculada na leitura (`sync_course_completions`).

> O `feat/migration` ainda está sendo editado (mudanças não commitadas em `services.py`, `models.py`, rotas, frontend, mais `schedule.py` e `edit-course.html`). O inventário abaixo é de 31/10/2026. Congele o contrato antes da reescrita (pergunta em aberto na seção 11).

### 1.3 Inventário da API (contrato a preservar)

| Método e rota | Papel | Arquivo |
| --- | --- | --- |
| `GET /api/session` | todos | `routes/session.py` |
| `POST /api/setup` | só enquanto não houver usuário | `routes/session.py` |
| `POST /api/login`, `POST /api/logout` | todos / logado | `routes/session.py` |
| `GET /api/courses`, `POST /api/courses` | aluno ou admin / admin | `routes/courses.py` |
| `GET /api/courses/<id>`, `PUT /api/courses/<id>` | aluno ou admin / admin | `routes/courses.py` |
| `POST /api/courses/<id>/questions` | admin | `routes/courses.py` |
| `POST /api/courses/<id>/answers` | aluno | `routes/courses.py` |
| `POST /api/courses/<id>/lessons` | admin | `routes/lessons.py` |
| `GET /api/courses/<id>/lessons/<id>`, `PUT …` | aluno ou admin / admin | `routes/lessons.py` |
| `POST /api/courses/<id>/lessons/<id>/complete` | aluno | `routes/lessons.py` |
| `GET /api/admin/progress`, `GET/POST /api/admin/users`, `PUT /api/admin/users/<id>/password` | admin | `routes/admin.py` |

São 18 endpoints, todos JSON, sem streaming, upload ou websocket.

---

## 2. Arquitetura-alvo

```
Navegador
   │  https://<dominio>
   ▼
┌──────────────────────────────────────────────┐
│ Um único Cloudflare Worker ("todayclass")    │
│  plano Free                                   │
│  • Static Assets: frontend/public            │
│  • /api/*  → app Hono (TypeScript)           │
│      ├─ sessão: cookie HMAC novo             │
│      ├─ senhas: PBKDF2 (WebCrypto)           │
│      └─ dados: Drizzle + @libsql/client/web  │
└──────────────────────┬───────────────────────┘
                       │ HTTP
                       ▼
                     Turso
              (importado do courses.db
               do PythonAnywhere)
```

D1, R2, KV, Durable Objects, Queues e Cron **não** entram agora. Cron só faria sentido se o recálculo de conclusão saísse do caminho de leitura (seção 4.6).

**Por quê um Worker em TypeScript, e não Flask na Cloudflare:** Python Workers existem (Pyodide), mas o driver atual (`sqlalchemy-libsql` / `libsql-experimental`) é extensão nativa e não roda lá **[verificar o estado do Python Workers]**. A API tem cerca de 600 linhas e 18 rotas JSON. Reescrever em Hono é menor do que adaptar Flask + driver.

**Por quê Turso, e não D1 agora:** o schema-alvo já é SQLite/libSQL, o `feat/migration` já fala com o Turso, e o volume (dois usuários) cabe no plano gratuito do Turso **[verificar limites]**. D1 continuaria no mesmo dialeto, mas exigiria outro export/import e reescrever transações. Fica para depois (seção 4.7).

---

## 3. Configuração do Worker

### 3.1 Estrutura sugerida

Diretório novo, `worker/`, para não quebrar `frontend/` e `backend/` durante a transição:

```
worker/
  package.json
  wrangler.jsonc
  tsconfig.json
  drizzle.config.ts
  scripts/hash-password.mjs   # gera hashes PBKDF2 no cutover (seção 5.2)
  src/
    index.ts
    routes/session.ts
    routes/courses.ts
    routes/lessons.ts
    routes/admin.ts
    auth/session-cookie.ts
    auth/csrf.ts
    auth/passwords.ts        # só PBKDF2, sem scrypt
    domain/schedule.ts       # porta de schedule.py
    domain/validation.ts
    db/schema.ts
    db/client.ts             # Turso
  test/
```

Os assets continuam em `frontend/public`.

### 3.2 `worker/wrangler.jsonc`

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "todayclass",
  "main": "src/index.ts",
  "compatibility_date": "2026-10-01",
  // Sem nodejs_compat: Hono, Drizzle, @libsql/client/web e WebCrypto não precisam de node:*.

  "assets": {
    "directory": "../frontend/public",
    "binding": "ASSETS",
    "run_worker_first": ["/api/*"],
    "not_found_handling": "404-page"   // [verificar] se existe 404.html; senão "none"
    // "html_handling": "auto-trailing-slash" é o padrão. [verificar] se /login.html?next=...
    // continua funcionando ou redireciona para /login sem perder a query.
  },

  "vars": {
    "APP_TIMEZONE": "America/Sao_Paulo",
    "PBKDF2_ITERATIONS": "10000"   // [verificar] seção 5.2
  },
  // Secrets: SESSION_SECRET, TURSO_DATABASE_URL, TURSO_AUTH_TOKEN

  "observability": { "enabled": true },

  "env": {
    "preview": {
      "name": "todayclass-preview"
      // outro TURSO_DATABASE_URL, banco de preview
    }
  }
}
```

Notas:

- `compatibility_date`: use a data do dia em que o projeto for criado. O `frontend/wrangler.toml` já usa `2026-10-01`.
- `_headers`: o arquivo `frontend/public/_headers` (nosniff, `Referrer-Policy`, `X-Frame-Options`) **[verificar]** vale para assets. Para a API, defina os headers no Hono (`secureHeaders`).

### 3.3 `worker/package.json`

```json
{
  "name": "todayclass-worker",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy",
    "deploy:preview": "wrangler deploy --env preview",
    "cf-typegen": "wrangler types",
    "test": "vitest run",
    "db:generate": "drizzle-kit generate",
    "db:pull": "drizzle-kit pull"
  },
  "dependencies": {
    "hono": "^4.13.14",
    "drizzle-orm": "^0.45.4",
    "@libsql/client": "^0.18.0"
  },
  "devDependencies": {
    "wrangler": "^4.156.0",
    "drizzle-kit": "^0.31.11",
    "vitest": "<versão compatível com o pool>",
    "@cloudflare/vitest-pool-workers": "<verificar>",
    "typescript": "^5"
  }
}
```

Versões consultadas no npm em 31/10/2026: `wrangler` 4.156.0, `hono` 4.13.14, `drizzle-orm` 0.45.4, `drizzle-kit` 0.31.11, `@libsql/client` 0.18.0. **[verificar]** qual versão do `vitest` o `@cloudflare/vitest-pool-workers` aceita.

### 3.4 Esqueleto do `src/index.ts`

```ts
import { Hono } from 'hono';
import { secureHeaders } from 'hono/secure-headers';
import { sessionRoutes } from './routes/session';
import { courseRoutes } from './routes/courses';
import { lessonRoutes } from './routes/lessons';
import { adminRoutes } from './routes/admin';
import { loadSession, validateCsrf } from './auth/csrf';

const app = new Hono<{ Bindings: Env }>().basePath('/api');

app.use('*', secureHeaders());
app.use('*', loadSession);
app.use('*', validateCsrf);

app.route('/', sessionRoutes);
app.route('/courses', courseRoutes);
app.route('/courses/:courseId/lessons', lessonRoutes);
app.route('/admin', adminRoutes);

app.notFound((context) => context.json({ error: 'Não encontrado.' }, 404));
app.onError((error, context) => {
  console.error(error);
  return context.json({ error: 'Não foi possível concluir o pedido.' }, 500);
});

export default app;
```

Reproduza as mensagens de `ERROR_MESSAGES` em `todayclass/__init__.py` (401, 403, 404, 405). O frontend as exibe.

---

## 4. Banco de dados: do PythonAnywhere para o Turso

O schema-alvo é o de `backend/todayclass/models.py` (branch `feat/migration`): tabelas `course`, `lesson`, `question`, `link` e `user`.

| Tabela | Colunas |
| --- | --- |
| `course` | `id`, `name VARCHAR(120)`, `completed_at DATETIME` |
| `lesson` | `id`, `course_id`, `day`, `title VARCHAR(120)`, `content TEXT`, `is_completed BOOLEAN`, `completed_at DATETIME` |
| `question` | `id`, `course_id`, `position`, `prompt VARCHAR(500)`, `answer TEXT` |
| `link` | `id`, `title VARCHAR(100)`, `url VARCHAR(255)`, `lesson_id` |
| `user` | `id`, `username VARCHAR(80)` único, `password_hash VARCHAR(255)`, `role VARCHAR(20)` |

A cópia local `courses.db` (worktree `main`, conferida em 31/10/2026) **já está nesse formato**: `user` 2, `course` 2, `lesson` 1, `link` 1, e a tabela `question` existe. O arquivo **no PythonAnywhere** é a fonte da verdade e pode divergir (schema antigo, ou mais linhas). Não importe a cópia local sem comparar com o servidor.

### 4.1 Exportar o `courses.db` de produção

No console do PythonAnywhere, na pasta do app, com o site parado ou num horário sem uso (o SQLite pode estar com WAL):

```bash
sqlite3 courses.db "PRAGMA wal_checkpoint(FULL);"
sqlite3 courses.db ".dump" > courses-export.sql
sqlite3 courses.db "
SELECT 'user', COUNT(*) FROM user
UNION ALL SELECT 'course', COUNT(*) FROM course
UNION ALL SELECT 'lesson', COUNT(*) FROM lesson
UNION ALL SELECT 'link', COUNT(*) FROM link
UNION ALL SELECT 'question', COUNT(*) FROM question;
" > counts-before.txt
sqlite3 courses.db ".schema" > schema-before.sql
```

Se `question` ainda não existir, o `COUNT` falha. Anote isso e siga para a transformação. Baixe `courses-export.sql`, `counts-before.txt` e `schema-before.sql`. Não commite esses arquivos (têm hashes de senha e o conteúdo das aulas).

Recrie o arquivo localmente:

```bash
rm -f courses-export.db
sqlite3 courses-export.db < courses-export.sql
```

### 4.2 Transformar para o schema-alvo, se o arquivo for antigo

O `app.py` trata dois formatos. Confira qual é o do dump:

```bash
sqlite3 courses-export.db "SELECT name FROM pragma_table_info('course');"
```

**Formato novo** (é o caso da cópia local): `course` tem `name` e `completed_at`, e **não** tem `day`. Existem `lesson`, `link`, `question` e `user`. Não há transformação de linhas. Pule para a seção 4.3. Se faltar só `course.completed_at` ou a tabela `question`, aplique o bloco "completar o schema" abaixo.

**Formato antigo:** `course` tem a coluna `day` (cada linha é uma aula) e `link` tem `course_id` em vez de `lesson_id`. É o que `rename_legacy_tables` / `copy_legacy_rows` em `app.py` converte. Rode o SQL abaixo numa cópia (`cp courses-export.db courses-ready.db`), não no original:

```sql
BEGIN;

ALTER TABLE course RENAME TO legacy_course;
ALTER TABLE link RENAME TO legacy_link;

CREATE TABLE course (
  id INTEGER NOT NULL PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  completed_at DATETIME
);

CREATE TABLE lesson (
  id INTEGER NOT NULL PRIMARY KEY,
  course_id INTEGER NOT NULL,
  day INTEGER NOT NULL,
  title VARCHAR(120) NOT NULL,
  content TEXT NOT NULL,
  is_completed BOOLEAN NOT NULL,
  completed_at DATETIME,
  FOREIGN KEY(course_id) REFERENCES course (id)
);

CREATE TABLE link (
  id INTEGER NOT NULL PRIMARY KEY,
  title VARCHAR(100) NOT NULL,
  url VARCHAR(255) NOT NULL,
  lesson_id INTEGER NOT NULL,
  FOREIGN KEY(lesson_id) REFERENCES lesson (id)
);

CREATE TABLE question (
  id INTEGER NOT NULL PRIMARY KEY,
  course_id INTEGER NOT NULL,
  position INTEGER NOT NULL,
  prompt VARCHAR(500) NOT NULL,
  answer TEXT,
  FOREIGN KEY(course_id) REFERENCES course (id)
);

-- A tabela user do formato antigo já tem o mesmo formato. Não recrie.

INSERT INTO course (name) VALUES ('Curso geral');

INSERT INTO lesson (id, course_id, day, title, content, is_completed, completed_at)
SELECT id,
       (SELECT id FROM course WHERE name = 'Curso geral' ORDER BY id LIMIT 1),
       day,
       'Aula ' || day,
       content,
       COALESCE(is_completed, 0),
       completed_at
FROM legacy_course;

INSERT INTO link (id, title, url, lesson_id)
SELECT id, title, url, course_id
FROM legacy_link
WHERE course_id IN (SELECT id FROM lesson);

DROP TABLE legacy_link;
DROP TABLE legacy_course;

COMMIT;
```

Isso espelha `copy_legacy_lessons` e `copy_legacy_links`: o título vira `Aula <dia>` porque a tabela antiga não tem título, e os links só entram se o `course_id` antigo existir como aula. O nome `Curso geral` é o `GENERIC_COURSE_NAME` do `app.py`.

**Completar o schema** (banco já novo, mas anterior às colunas de pergunta / conclusão de curso):

```sql
-- só se a coluna não existir
ALTER TABLE course ADD COLUMN completed_at DATETIME;

CREATE TABLE IF NOT EXISTS question (
  id INTEGER NOT NULL PRIMARY KEY,
  course_id INTEGER NOT NULL,
  position INTEGER NOT NULL,
  prompt VARCHAR(500) NOT NULL,
  answer TEXT,
  FOREIGN KEY(course_id) REFERENCES course (id)
);
```

Não apague nem reescreva `password_hash` nesta etapa. O reset é outro passo, no cutover (seção 5.2), para a validação de contagem ainda poder comparar os hashes.

Conferência rápida depois da transformação:

```bash
sqlite3 courses-ready.db "
SELECT 'user', COUNT(*) FROM user
UNION ALL SELECT 'course', COUNT(*) FROM course
UNION ALL SELECT 'lesson', COUNT(*) FROM lesson
UNION ALL SELECT 'link', COUNT(*) FROM link
UNION ALL SELECT 'question', COUNT(*) FROM question;
"
sqlite3 courses-ready.db "PRAGMA foreign_key_check;"
```

No formato antigo, `lesson` deve ter a mesma contagem que o `course` de origem, e `link` a mesma contagem que o `link` de origem (menos linhas cujo `course_id` não virou aula). No formato novo, as cinco contagens devem bater com `counts-before.txt`. `PRAGMA foreign_key_check` deve voltar vazio.

### 4.3 Importar no Turso

Com a [CLI do Turso](https://docs.turso.tech/cli/introduction) logada. O README do `feat/migration` já usa `--from-file`:

```bash
turso db create todayclass --from-file courses-ready.db
turso db show todayclass --url
turso db tokens create todayclass
```

`courses-ready.db` é o arquivo transformado, ou o export puro se ele já estava no formato novo. **[verificar]** se a CLI atual ainda aceita `--from-file` e se recusa tabelas internas (`sqlite_sequence` em geral pode ir junto).

Banco de preview, separado:

```bash
turso db create todayclass-preview --from-file courses-ready.db
```

**[verificar]** a flag `--from-db` se for mais simples clonar depois (`turso db create todayclass-preview --from-db todayclass`).

### 4.4 Validar as contagens

```bash
turso db shell todayclass "
SELECT 'user' AS t, COUNT(*) AS n FROM user
UNION ALL SELECT 'course', COUNT(*) FROM course
UNION ALL SELECT 'lesson', COUNT(*) FROM lesson
UNION ALL SELECT 'link', COUNT(*) FROM link
UNION ALL SELECT 'question', COUNT(*) FROM question;
"
```

Compare com a contagem do `courses-ready.db` (não só com a de antes da transformação: no formato antigo, `course` deixa de ser "uma linha por aula").

Além da contagem, confira o conteúdo:

```bash
turso db shell todayclass "
SELECT id, name, completed_at FROM course ORDER BY id;
SELECT id, course_id, day, title, length(content), is_completed FROM lesson ORDER BY id;
SELECT id, lesson_id, title, url FROM link ORDER BY id;
SELECT id, username, role, substr(password_hash, 1, 12) FROM user ORDER BY id;
"
```

O prefixo `scrypt:32768` nos hashes confirma que o import preservou as senhas antigas. Elas serão substituídas no cutover. Abra uma aula no `turso db shell` e compare o HTML com o site no PythonAnywhere.

Se algo divergir, apague o banco (`turso db destroy todayclass`) e importe de novo. Não há tráfego de produção nesse banco até o cutover.

### 4.5 Como o Worker lê o Turso

Espelhe `models.py` no Drizzle. O caminho mais seguro é gerar o schema a partir do banco importado:

```bash
cd worker
# drizzle.config.ts com dialect "turso" e as credenciais
npx drizzle-kit pull
```

| Coluna | Como o SQLAlchemy grava | No Drizzle |
| --- | --- | --- |
| `DateTime` (`completed_at`) | texto `YYYY-MM-DD HH:MM:SS.ffffff`, UTC sem fuso | `text()` com conversão própria. Não use `integer({ mode: 'timestamp' })` |
| `Boolean` (`is_completed`) | inteiro 0/1 | `integer({ mode: 'boolean' })` |
| `String(n)` | `VARCHAR(n)` (o SQLite não impõe o tamanho) | `text()`, limites validados em código |

```ts
import { createClient } from '@libsql/client/web';
import { drizzle } from 'drizzle-orm/libsql';

export function databaseFor(env: Env) {
  const client = createClient({ url: env.TURSO_DATABASE_URL, authToken: env.TURSO_AUTH_TOKEN });
  return drizzle(client);
}
```

- Use `@libsql/client/web` (HTTP). A entrada padrão tenta carregar binário nativo.
- **[verificar]** se o cliente web aceita `libsql://…` ou se a URL precisa ser `https://…`.

Escritas que hoje são uma transação SQLAlchemy (`create_lesson` com links, `replace_questions`, `record_answers`) devem ir em `client.batch([...], 'write')` ou `db.transaction()` do Drizzle. **[verificar]** transações interativas pelo HTTP do Turso.

### 4.6 Conclusão de curso e fuso

`catalog_for` grava `completed_at` durante um GET (`sync_course_completions`). Pode continuar assim. O mais limpo é gravar só nas escritas que mudam o estado. Um Cron Trigger só entra se a regra passar a depender só da passagem do tempo.

`schedule.py` usa `ZoneInfo('America/Sao_Paulo')`. No Worker:

```ts
export function saoPauloDate(moment: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Sao_Paulo' }).format(moment);
}
```

Porte os testes de `backend/tests/test_course_progress.py` (ainda não commitado no `feat/migration`).

### 4.7 D1, depois (opcional, fora do plano)

Decisão atual: ficar no Turso. Se um dia for para o D1:

```bash
turso db shell todayclass .dump > dump.sql
npx wrangler d1 create todayclass
npx wrangler d1 execute todayclass --remote --file=dump.sql
```

**[verificar]** se o D1 aceita o dump (transações, `sqlite_sequence`). No código, troca-se `drizzle-orm/libsql` por `drizzle-orm/d1`. O D1 não tem transação interativa: as escritas da seção 4.5 viram `db.batch([...])`.

---

## 5. Autenticação, sessão e senhas

### 5.1 Sessão

Cookie novo (`todayclass_session`), assinado com HMAC-SHA256 via `hono/cookie` (`setSignedCookie` / `getSignedCookie`), payload `{ userId, csrfToken, issuedAt }`, `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`.

Não há compatibilidade com o cookie do Flask. Na troca, admin e aluno entram de novo. Combinado.

O contrato do frontend não muda: `GET /api/session` devolve `{ user, needs_setup, csrf_token }`, e os métodos inseguros exigem `Content-Type: application/json` e `X-CSRF-Token`. `frontend/public/js/api.js` e `session.js` ficam como estão.

`needs_setup` continua "não existe nenhuma linha em `user`". Como o import traz os dois usuários, `/api/setup` responde 404. O reset **não** apaga as linhas (seção 5.2).

### 5.2 Senhas: reset no cutover, PBKDF2 no Worker

Os hashes atuais (`scrypt:32768:8:1$…`) não são verificados no Worker. O plano Free fica viável porque o login só calcula PBKDF2.

Formato gravado em `user.password_hash`:

```
pbkdf2_sha256$<iterações>$<salt base64url>$<hash base64url>
```

Parâmetros: PBKDF2-HMAC-SHA256, salt de 16 bytes, hash de 256 bits, via `crypto.subtle` (WebCrypto), que existe no Workers sem `nodejs_compat`.

**Iterações: começar com 10.000 e medir. [verificar]** O plano Free limita o CPU por requisição (na ordem de 10 ms; confirme o número atual). O PBKDF2 no Workers também tem um teto de iterações **[verificar, historicamente 100.000]**. 10.000 é um ponto de partida para caber nesse teto, não uma recomendação de hardening: o OWASP pede bem mais para PBKDF2-SHA256, e isso não cabe no Free. Para dois usuários e sem cadastro público, o limite aceito é esse. Se o login no preview estourar o CPU, baixe as iterações e grave de novo. O valor usado tem de ser o mesmo na geração do hash e em `PBKDF2_ITERATIONS`.

Gerar o hash (Node 20+, WebCrypto, para rodar na máquina, não no Worker):

```js
// worker/scripts/hash-password.mjs
import { webcrypto } from 'node:crypto';

const iterations = 10000; // [verificar] igual a PBKDF2_ITERATIONS

const password = process.argv[2];
if (!password || password.length < 8) {
  console.error('Uso: node scripts/hash-password.mjs "<senha com 8+ caracteres>"');
  process.exit(1);
}

const salt = webcrypto.getRandomValues(new Uint8Array(16));
const key = await webcrypto.subtle.importKey(
  'raw',
  new TextEncoder().encode(password),
  'PBKDF2',
  false,
  ['deriveBits'],
);
const bits = await webcrypto.subtle.deriveBits(
  { name: 'PBKDF2', hash: 'SHA-256', salt, iterations },
  key,
  256,
);
const saltB64 = Buffer.from(salt).toString('base64url');
const hashB64 = Buffer.from(new Uint8Array(bits)).toString('base64url');
process.stdout.write(`pbkdf2_sha256$${iterations}$${saltB64}$${hashB64}\n`);
```

Verificação no Worker (esboço):

```ts
export async function passwordMatches(password: string, stored: string): Promise<boolean> {
  const [scheme, iterationsText, saltB64, hashB64] = stored.split('$');
  if (scheme !== 'pbkdf2_sha256' || !iterationsText || !saltB64 || !hashB64) return false;
  const salt = base64UrlToBytes(saltB64);
  const expected = base64UrlToBytes(hashB64);
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveBits'],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt, iterations: Number(iterationsText) },
    key,
    expected.length * 8,
  );
  return timingSafeEqual(new Uint8Array(bits), expected);
}
```

**Procedimento do reset** (depois que a seção 4.4 passou, de preferência já com o Worker de preview no ar):

1. Gere uma senha temporária para o admin e outra para o aluno (mínimo 8 caracteres, a mesma regra de `validation.py`). Não reutilize a senha antiga: o Worker não conseguiria conferi-la.
2. `node scripts/hash-password.mjs "<senha>"` para cada uma.
3. No Turso de **preview**, aplique e teste o login antes de mexer na produção:

```sql
UPDATE user SET password_hash = '<hash do admin>' WHERE username = '<username do admin>';
UPDATE user SET password_hash = '<hash do aluno>' WHERE username = '<username do aluno>';
SELECT username, substr(password_hash, 1, 15) FROM user;
```

O prefixo tem de ser `pbkdf2_sha256$`, e as duas linhas precisam mudar. `username` e `role` ficam iguais, então o progresso dos cursos (que não é por usuário) não se mexe.

4. Entre no preview com as duas contas. Confira o CPU do `POST /api/login` em `wrangler tail` ou na Observability. Se estourar, reduza as iterações, gere os hashes de novo e repita.
5. No cutover, rode os mesmos `UPDATE` no Turso de produção (`todayclass`).
6. Entregue as senhas temporárias por um canal fora do site. O admin pode trocar a senha do aluno no painel (`PUT /api/admin/users/<id>/password`), que passa a gravar PBKDF2 também.

Não use `POST /api/setup` para isso: ele só funciona com a tabela `user` vazia. Não apague os usuários: os usernames deixariam de existir e o `/setup` criaria só o admin.

### 5.3 Proteção extra

- **Rate limit no `/api/login`** (não existe hoje): binding de Rate Limiting do Workers **[verificar]** ou regra de WAF no domínio.
- O HTML da aula é renderizado com `innerHTML` (`frontend/public/js/pages/lesson.js`). Uma `Content-Security-Policy` no `_headers` (permitindo `fonts.googleapis.com` e `fonts.gstatic.com`) reduz o impacto de um HTML colado por engano.

---

## 6. Variáveis de ambiente e segredos

Produção hoje só tem `SECRET_KEY` no PythonAnywhere (WSGI). Ela **não** é reaproveitada: o cookie muda de formato.

| Secret / var | Onde nasce | Como definir |
| --- | --- | --- |
| `SESSION_SECRET` | valor novo (`openssl rand -hex 32`) | `wrangler secret put SESSION_SECRET` |
| `TURSO_DATABASE_URL` | `turso db show todayclass --url` | `wrangler secret put` (a URL não é sigilosa; pode ir em `vars`) |
| `TURSO_AUTH_TOKEN` | `turso db tokens create todayclass` | `wrangler secret put TURSO_AUTH_TOKEN` |
| `APP_TIMEZONE` | `America/Sao_Paulo` | `vars` no `wrangler.jsonc` |
| `PBKDF2_ITERATIONS` | `10000` até a medição da seção 5.2 | `vars` |

- Local: `worker/.dev.vars` (não commitar).
- Preview: `wrangler secret put <NOME> --env preview`, apontando para `todayclass-preview`.
- Tipos: `wrangler types` gera `Env`.
- Não há `API_ORIGIN`: o proxy deixa de existir.

Se algum projeto Vercel ou Pages tiver sido criado como experimento do `feat/migration`, apague as variáveis de lá na limpeza. Eles não são produção.

---

## 7. Domínio e DNS

O repositório não registra o domínio. Em produção o site está no PythonAnywhere (subdomínio `*.pythonanywhere.com` ou um domínio próprio apontando para lá). Isso continua em aberto (seção 11).

- **Sem domínio próprio:** o Worker responde em `todayclass.<subdomínio>.workers.dev`. O cookie `Secure` funciona. O aluno troca a URL e entra de novo.
- **Com domínio próprio na Cloudflare:** a zona precisa usar os nameservers da Cloudflare. Custom Domain no Worker: `"routes": [{ "pattern": "curso.exemplo.com", "custom_domain": true }]`. O certificado é automático **[verificar]**.
- Entrar de novo depois da troca é esperado (cookie novo e, se a URL mudar, origem nova). Avise mesmo assim, inclusive se o site estiver na tela de início do celular (`frontend/public/brand/manifest.json`).
- Enquanto o PythonAnywhere existir, um redirect HTTP de lá para a URL nova evita favorito quebrado. **[verificar]** se o plano gratuito do PythonAnywhere deixa configurar isso.

---

## 8. CI/CD e ambientes de preview

O repositório não tem remoto nem CI. A escolha (Workers Builds ou GitHub Actions) depende de onde o git vai morar (seção 11).

### 8.1 Workers Builds

Root `worker`, build `npm ci && npm test`, deploy `npx wrangler deploy`. Previews de branch **[verificar]** se usam o `env.preview` ou o ambiente padrão. O preview não pode apontar para o Turso de produção.

### 8.2 GitHub Actions

```yaml
# .github/workflows/worker.yml
name: worker
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test-and-deploy:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: worker
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm ci
      - run: npm test
      - name: Deploy preview
        if: github.event_name == 'pull_request'
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          workingDirectory: worker
          command: deploy --env preview
      - name: Deploy production
        if: github.ref == 'refs/heads/main'
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          workingDirectory: worker
          command: deploy
```

- Token com permissão "Edit Cloudflare Workers".
- **[verificar]** as versões de `actions/checkout`, `actions/setup-node` e `cloudflare/wrangler-action`.

### 8.3 Testes

- Porte os pytest de `backend/tests/` para `vitest` com `@cloudflare/vitest-pool-workers`.
- Testes de contrato HTTP contra o Flask (`python backend/dev.py`) e contra `wrangler dev` pegam divergência de status e JSON.
- `frontend/tests/proxy.test.js` sai junto com a Pages Function, quando o proxy deixar de existir.

---

## 9. Plano em fases (checklist)

### Fase 0. O que ainda falta decidir

Já decidido: frontend estático, plano Free, Turso, reset de senha, novo login na troca. Continua em aberto (seção 11):

- [ ] Domínio: `workers.dev` ou domínio próprio com DNS na Cloudflare.
- [ ] Onde o repositório fica, e se o CI é Workers Builds ou GitHub Actions.
- [ ] Congelar o contrato da API do `feat/migration` (ainda há edição em paralelo).
- [ ] Se `backend/` em Python sai depois da migração.
- [ ] Se haverá upload de imagem ou vídeo no futuro.

### Fase 1. Dados: PythonAnywhere → Turso

- [ ] Parar o site (ou escolher um horário parado) e fazer checkpoint do WAL.
- [ ] Exportar `courses.db`, o schema e as contagens (seção 4.1).
- [ ] Classificar o schema: formato novo ou antigo (`course.day`).
- [ ] Se antigo, rodar o SQL da seção 4.2 e o `foreign_key_check`.
- [ ] `turso db create todayclass --from-file …` e o mesmo para `todayclass-preview`.
- [ ] Validar contagens e uma amostra de aulas (seção 4.4). Guardar o dump fora do git.

### Fase 2. Worker (assets + Hono) contra o Turso de preview

- [ ] `worker/` com `wrangler.jsonc` apontando `assets.directory` para `../frontend/public`. Sem `nodejs_compat`.
- [ ] Schema Drizzle via `drizzle-kit pull` do preview.
- [ ] Portar `validation.py`, `schedule.py`, `serializers.py` e `services.py`, com os testes.
- [ ] Portar as rotas na ordem `session` → `courses` → `lessons` → `admin`, com as mesmas mensagens em pt-BR.
- [ ] Cookie HMAC + CSRF por header (seção 5.1). Login só com PBKDF2 (seção 5.2).
- [ ] Reset de senha **no preview** e teste das duas contas. Anotar o CPU do login e ajustar iterações se precisar.
- [ ] Rate limit no login.
- [ ] Conferir `html_handling` (`/login.html?next=…`), `_headers` e 404.

Não há fase de proxy para a Vercel. A Vercel não está em produção. A Pages Function existente serve só como referência de "mesmo domínio para o cookie", e o Worker único já resolve isso.

### Fase 3. Troca

- [ ] Avisar o aluno: URL nova (se houver) e senha temporária. O login antigo deixa de valer.
- [ ] Backup final do PythonAnywhere (`PRAGMA wal_checkpoint` + `.dump`) e, se o Turso de produção já tiver ensaio, `turso db shell todayclass .dump`.
- [ ] Reimportar se o `courses.db` mudou desde a fase 1, e repetir a validação de contagem.
- [ ] `UPDATE` dos `password_hash` no Turso de produção (seção 5.2).
- [ ] `wrangler deploy` com os secrets de produção.
- [ ] Entrar como admin e como aluno. Abrir a aula, marcar conclusão só se for o caso de teste combinado (a conclusão é do curso, não dá para desfazer sem editar o banco).
- [ ] Apontar o domínio, quando existir.
- [ ] Monitorar com `wrangler tail` (erros e CPU do login).
- [ ] Rollback de código: `wrangler rollback` **[verificar]**. Rollback de dados: o PythonAnywhere continua no ar até a fase 4, com o `courses.db` intacto. Não desligue o PythonAnywhere no mesmo dia.

### Fase 4. Limpeza

- [ ] Depois de alguns dias estáveis, desligar o web app no PythonAnywhere. Manter uma cópia do `courses.db`.
- [ ] Se existir projeto experimental na Vercel ou no Pages, apagar e revogar tokens.
- [ ] Remover `frontend/functions/`, `frontend/tests/proxy.test.js`, `backend/vercel.json`, `backend/.vercelignore` e `backend/api/` quando o contrato estiver no Worker.
- [ ] Decidir o destino de `backend/` e de `app.py` (seção 11).
- [ ] Reescrever o `README.md` (hoje descreve PythonAnywhere no `main` e Vercel + Pages no `feat/migration`).

### Fase 5 (opcional, sem data). Turso → D1

- [ ] Só se a decisão da seção 4.7 mudar. Export, import, `batch` no lugar de transação interativa, preview primeiro.

---

## 10. Riscos

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| O `courses.db` do PythonAnywhere está no schema antigo e a transformação junta tudo num "Curso geral" | alto | Detectar `course.day` antes de importar. Conferir contagens e o HTML de uma aula. Não destruir o arquivo de origem |
| O arquivo muda entre o export e o cutover | alto | Novo dump na fase 3, com o site parado |
| A reescrita Python → TS muda desbloqueio, conclusão ou validação | alto | Portar os pytest e rodar contrato contra os dois backends |
| PBKDF2 estoura o CPU do plano Free | médio | Medir no preview (seção 5.2) e baixar iterações antes do cutover. **[verificar]** o limite |
| `DateTime` do SQLAlchemy lido errado em TS | médio | `drizzle-kit pull` + comparar `completed_at` com o shell do Turso |
| Preview escreve no Turso de produção | médio | `env.preview` com `todayclass-preview` |
| `feat/migration` ainda muda o contrato | médio | Congelar antes da fase 2 |
| HTML da aula via `innerHTML` | baixo (só o admin escreve) | CSP no `_headers` |
| Login sem rate limit | baixo/médio | Rate Limiting ou WAF |

---

## 11. Perguntas em aberto

1. **Domínio e DNS.** O site no PythonAnywhere usa `*.pythonanywhere.com` ou um domínio próprio? Esse domínio pode ter o DNS na Cloudflare? Sem isso, a publicação fica em `workers.dev`.
2. **Repositório e CI.** Não há remoto. O git vai para o GitHub (ou GitLab)? O deploy é Workers Builds ou GitHub Actions?
3. **`backend/` e `app.py`.** Depois que o Worker estiver estável, o Flask sai do repositório ou fica como referência? Manter os dois é manter duas implementações da mesma regra.
4. **Uploads.** Há plano de subir imagem ou vídeo nas aulas? Hoje não existe storage de arquivo. Se a resposta for sim, o passo seguinte é um bucket R2 com URL assinada. Não entra nesta migração.
5. **Contrato da API.** O `feat/migration` ainda tem mudanças não commitadas (`schedule.py`, `edit-course.html`, serviços e rotas). Quando esse contrato pode ser congelado para a porta em Hono começar?

---

## Apêndice. Next.js não faz parte deste plano

O frontend permanece o HTML/JS de `frontend/public`. Não há etapa com Next.js, React nem `@opennextjs/cloudflare`.

Se um dia o frontend for reescrito em Next.js, o adaptador OpenNext (`@opennextjs/cloudflare`, 1.20.15 no npm em 31/10/2026; `next` 16.4.3) gera um Worker a partir do build, exige `nodejs_compat`, e não usa o runtime Edge do Next. Isso seria um projeto separado: outro `wrangler.jsonc`, `open-next.config.ts`, e atenção a `next/image`, ISR e tamanho do Worker no plano Free. Nada disso está no código atual, e nada disso bloqueia as fases acima.
