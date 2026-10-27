# DiáriaMente

Um curso por dia, no celular. Você escreve a aula, seu pai lê e marca como feita. O progresso fica num SQLite, e o site cabe no plano gratuito do [PythonAnywhere](https://www.pythonanywhere.com/).

## O que tem aqui

Tudo vive em [`app.py`](app.py). As páginas ficam em `templates/` e usam [Pico.css](https://picocss.com/), então o layout já nasce legível no telefone.

| Rota | Quem entra | O que faz |
| --- | --- | --- |
| `/setup` | ninguém, só na primeira vez | cria a conta de admin |
| `/login` | os dois | entra no site |
| `/day/<dia>` | aluno ou admin | lê a aula e os links |
| `/success` | aluno ou admin | confirma que o dia foi concluído |
| `/secret-admin-dashboard` | só admin | vê o progresso e cria logins |

O aluno cai no primeiro dia ainda não concluído. O admin cai no painel. "Mark as Done" só aparece para o aluno, para um preview seu não marcar o dia dele sem querer.

O conteúdo da aula é HTML. Na página ele é renderizado de propósito, então escreva o texto você mesmo e não cole HTML de outra pessoa.

## Rodar na sua máquina

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Abra [http://127.0.0.1:5000/setup](http://127.0.0.1:5000/setup), crie o admin e, no painel, crie o login do seu pai. A senha precisa ter pelo menos 8 caracteres.

O banco `courses.db` aparece ao lado do `app.py`. Se ainda não existir nenhuma aula, o app cria o dia 1 só para você ver o formato.

## Publicar no PythonAnywhere

1. Crie um web app Flask apontando para esta pasta e para o virtualenv.
2. No arquivo WSGI, defina a chave **antes** de importar o app:

```python
import os
os.environ["SECRET_KEY"] = "um-valor-longo-e-aleatorio"
from app import app as application
```

3. No console, com o virtualenv ativo: `pip install -r requirements.txt`.
4. Recarregue o site e visite `/setup`.

Sem `SECRET_KEY`, o processo para na hora. Localmente o `python app.py` usa uma chave só de desenvolvimento. Não leve essa chave para o ar.

O cookie de sessão no PythonAnywhere vai com `Secure`, `HttpOnly` e `SameSite=Lax`. O banco continua no diretório do projeto, que é gravável no plano gratuito.

## Contas

Há dois papéis, `admin` e `student`, na tabela `User`. A senha é gravada com hash. Não existe cadastro público: depois do primeiro admin, `/setup` some. Se alguém esquecer a senha, o admin define outra no painel.

O progresso é do curso, não de cada pessoa. Um aluno, um dia, uma conclusão.
