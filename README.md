# WFM Atacadão-Protótipo

Protótipo funcional da **Plataforma de Gestão de Força de Trabalho para Atacadões** (Engenharia de Software I).
Implementa os requisitos de sistema **RS01 a RS18** do documento de especificação, em **Python + Django + PostgreSQL**
com **renderização no servidor e sem JavaScript**, pensado para terminais de loja com hardware modesto.

> **Status de verificação — leia antes de entregar.** O código e a suíte de testes (166 métodos de teste) foram escritos e
> conferidos por análise estática (compilação, linter, templates, rotas) e por execução isolada da lógica pura
> (CPF, escala, frequência). **A suíte completa ainda não foi executada com Django instalado.** Rode `make test`
> (ou `python manage.py test`) antes da apresentação e, se algo falhar, abra uma issue/corrija. Depois, apague este aviso.

## Início rápido (≈ 2 minutos)

Requisitos: **Python 3.12+**. Não é preciso instalar banco: sem configuração o projeto usa SQLite.

```bash
# Linux / macOS / WSL
make setup      # venv + dependências + migrações + dados de demonstração
make run        # http://127.0.0.1:8000
```

<details>
<summary>Sem <code>make</code> (Windows PowerShell ou manual)</summary>

```powershell
py -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
</details>

<details>
<summary>Com Docker (PostgreSQL 16 incluso)</summary>

```bash
docker compose up --build         # http://localhost:8000
```
O contêiner gera as migrações, aplica e carrega os dados de demonstração.
</details>

### Logins de demonstração (senha de todos: `demo1234`)

| Perfil | Matrícula | O que ver |
|--------|-----------|-----------|
| Gerente | `G001` | Painel, funcionários, tarefas, escalas, log de ponto, ocorrências, remanejamento, comunicados |
| Funcionário | `F001` … `F006` | Minhas tarefas, minha escala, registro de ponto, comunicados, mensagem ao gerente |
| Comprador | `C001` | Diretório de setores (só nome e setor) |

O login aceita **matrícula ou CPF** (com ou sem pontuação). Os CPFs do seed são sintéticos.

## Roteiro de demonstração (5 minutos)

1. **Gerente (`G001`)** → *Funcionários* → *Novo*: tente CPF inválido (`123.456.789-00`), nome começando com número e data de nascimento recente (RS01). Cadastre alguém e anote a senha temporária exibida.
2. *Escalas* → *Editar* um funcionário: marque os 7 dias (excede 36 h) ou *noite* seguida de *manhã* (descanso < 11 h) e veja a recusa (RS06/RS07).
3. *Tarefas* → *Nova tarefa*; depois *Painel* para ver a contagem por setor (RS04, RS10).
4. **Funcionário (`F001`)** → *Ponto* → registrar entrada; tente registrar entrada de novo (recusado). Observe que a hora é a do servidor (RS14). Em *Minhas tarefas*, inicie e conclua uma tarefa (RS13).
5. Volte ao **gerente** → *Log de ponto*: frequência e horas do período (RS09). Entre como funcionário e abra `/ponto/log/`: **403**.
6. Gerente → *Remanejar*: lista só quem está escalado no turno atual; o funcionário recebe o aviso em *Comunicados* (RS17, RS15).
7. **Comprador (`C001`)** → busque "cerveja": aparece o setor Bebidas, ramal e nomes, sem CPF ou cargo (RS18).

## Testes

```bash
make test                       # ou: python manage.py test --verbosity 2
python manage.py test apps.ponto   # um módulo
DB_ENGINE=postgres python manage.py test   # contra PostgreSQL (veja .env.example)
```

Os testes são nomeados por requisito (ex.: `RegistroTests` = RS14). A matriz completa RS → código → teste está em
[`docs/requisitos.md`](docs/requisitos.md). Também rodam no GitHub Actions (SQLite e PostgreSQL) a cada push.

## Estrutura

```
wfm-atacadao/
├── manage.py
├── requirements.txt          Django, psycopg, gunicorn, whitenoise
├── Makefile                  setup / run / test / docker-up
├── Dockerfile · docker-compose.yml · docker/entrypoint.sh
├── .env.example              todas as variáveis de configuração
├── .github/workflows/ci.yml  testes em SQLite e PostgreSQL
├── config/                   settings.py, urls.py, wsgi.py
├── apps/
│   ├── core/                 Filial, Setor, Cargo, Terminal · permissões · home · diretório (RS18) · seed_demo
│   ├── accounts/             Funcionario, login CPF/matrícula · RS01–RS03
│   ├── tarefas/              RS04, RS05, RS10, RS13
│   ├── escalas/              RS06, RS07, RS11, RS12, RS17
│   ├── ponto/                RS09, RS14 (log imutável)
│   └── comunicacao/          RS08, RS15, RS16
├── templates/                base.html, 403/404, includes/ (form, paginação)
├── static/css/app.css        único CSS (~6 KB)
└── docs/                     requisitos.md · arquitetura.md · diagramas/*.puml
```

Cada módulo: `models.py` (dados) · `forms.py` (validação) · `services.py` (**regras de negócio**) · `views.py` (finas) · `urls.py` · `templates/` · `tests.py`.
Detalhes e justificativas em [`docs/arquitetura.md`](docs/arquitetura.md).

## Configuração

Tudo por variáveis de ambiente (ou arquivo `.env`, copiado de `.env.example`). Os padrões servem para desenvolvimento.

| Variável | Padrão | Efeito |
|----------|--------|--------|
| `DB_ENGINE` | `sqlite` | `postgres` usa `POSTGRES_*` |
| `DJANGO_DEBUG` | `True` | Com `False`, `DJANGO_SECRET_KEY` passa a ser obrigatória |
| `WFM_ENFORCE_TERMINAL_IP` | `False` | `True`: ponto só de IPs cadastrados em *Terminal* |
| `WFM_TRUST_X_FORWARDED_FOR` | `False` | `True` apenas atrás de proxy confiável |

**Produção** (referência): defina `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_HTTPS=True`
e `DB_ENGINE=postgres`; rode `python manage.py migrate && python manage.py collectstatic --noinput` e sirva com
`gunicorn config.wsgi:application` atrás de Nginx (o WhiteNoise serve o CSS). O `docker/entrypoint.sh` usa
`runserver` e é só para demonstração.

Cadastro de filiais, setores, cargos e terminais: `/admin/` (crie um superusuário com `python manage.py createsuperuser`;
ele serve só para o admin, pois não tem filial).

## Git: primeiro commit

```bash
git init && git add . && git commit -m "Protótipo WFM Atacadão"
```

As migrações são geradas na primeira execução de `make setup`/`make test` (`apps/*/migrations/0001_initial.py`).
**Versione-as**: depois de rodar uma vez, `git add apps/*/migrations && git commit`. Em seguida, no CI, troque
`makemigrations --noinput` por `makemigrations --check --dry-run` para detectar modelos alterados sem migração.
O `.gitignore` já ignora `.venv/`, `db.sqlite3`, `.env` e caches.

## Decisões, premissas e limitações

O documento original deixa pontos em aberto e tem inconsistências; todas estão registradas em
[`docs/requisitos.md`](docs/requisitos.md). As principais premissas:

- **Turnos de 6 h** (manhã 06–12, tarde 12–18, noite 18–24), em `apps/core/turnos.py`.
- **Escala válida** = dentro do limite contratual semanal **e** com ≥ 11 h de descanso entre turnos.
- **"Tarefas do dia"** = prazo hoje; há uma coluna extra de atrasadas.
- **Ponto**: a hora vem do servidor (UTC no banco); entrada e saída se alternam; log imutável na aplicação
  (para produção, reforce no banco, veja `docs/arquitetura.md`).
- Os diagramas PlantUML do documento (7.1 e 7.3) tinham problemas e foram corrigidos em `docs/diagramas/`.

**Fora do escopo:** correção de ponto pelo gerente, exportação para folha, edição de tarefas, limite de tentativas de
login, troca de senha obrigatória, tela de cadastro de filiais/setores (use o admin).

## Documentação

- [`docs/requisitos.md`](docs/requisitos.md): matriz RS → código → teste, premissas, inconsistências do documento
- [`docs/arquitetura.md`](docs/arquitetura.md): camadas, decisões, fluxo, evolução (Fase 2)
- [`docs/diagramas/`](docs/diagramas/): arquitetura, estados da tarefa, casos de uso, modelo de dados (PlantUML)
