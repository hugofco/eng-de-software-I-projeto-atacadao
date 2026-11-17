# Arquitetura

Monolito modular em Django com renderização no servidor (SSR), conforme a seção 6 do documento.
Diagramas PlantUML em [`diagramas/`](diagramas/) (renderize em <https://www.plantuml.com/plantuml> ou com a extensão PlantUML do VS Code).

## Organização em camadas

Cada módulo (`apps/<modulo>/`) segue o mesmo padrão:

```
urls.py      rotas do módulo
views.py     finas: autenticação/perfil, leem a requisição e escolhem o template
forms.py     validação de entrada (restrições dos RS)
services.py  REGRAS DE NEGÓCIO (transições, limites, ponto...), sem HTTP: testáveis direto
models.py    dados e invariantes
templates/   HTML do módulo (SSR, sem JavaScript)
tests.py     testes do módulo, nomeados por requisito
```

| Módulo | Responsabilidade | RS |
|--------|------------------|----|
| `core` | Filial, Setor, Cargo, Terminal; permissões por perfil; home; diretório | RS18 |
| `accounts` | Usuário `Funcionario`, login por CPF/matrícula, cadastro/edição/desativação, auditoria | RS01–RS03 |
| `tarefas` | Tarefas, máquina de estados, painel | RS04, RS05, RS10, RS13 |
| `escalas` | Escala semanal, ocorrências, remanejamento | RS06, RS07, RS11, RS12, RS17 |
| `ponto` | Registro e log de ponto imutável, frequência | RS09, RS14 |
| `comunicacao` | Comunicados, leitura, mensagens ao gerente | RS08, RS15, RS16 |

Dependências de código entre módulos: `core` (modelos, perfis, turnos) ← `accounts` ← (`tarefas`, `comunicacao`, `ponto`) ← `escalas` (usa `comunicacao` para notificar). Não há importações circulares entre arquivos (verificado por análise estática). A única dependência "de volta" é `core.views`, que importa `accounts.models` (diretório do comprador) e, **dentro das funções**, serviços de tarefas/escalas/ponto, por ser o ponto de composição da tela inicial.

## Decisões de projeto

**Controle de acesso.** O decorador `perfil_required` (`core/permissions.py`) é a única porta de entrada das views protegidas: exige login, perfil permitido e filial vinculada; caso contrário responde 403 (`templates/403.html`). Regras que dependem do **dado** (ex.: "só tarefas atribuídas a mim", RS13) ficam nos `services`, não nas views.

**Escopo por filial desde o dia 1.** Todo dado de negócio chega à filial (direta ou via setor) e todas as consultas filtram pela filial do usuário. Um gerente da Loja A recebe 404 ao tentar abrir registros da Loja B. A Fase 2 (várias filiais) não exige mudar o núcleo.

**Autenticação.** `Funcionario` é o usuário (`AbstractBaseUser`), com `matricula` como `USERNAME_FIELD`. `MatriculaOuCpfBackend` aceita matrícula ou CPF (com/sem pontuação) e herda de `ModelBackend`, de modo que desativar um funcionário (RS03) também derruba sessões já abertas.

**Relógio do servidor (RS14).** O formulário de ponto só tem o campo `tipo`. A hora vem do `default=timezone.now` do campo `registrado_em` (`editable=False`), gravada em UTC (`USE_TZ=True`). `ip_do_cliente` só confia em `X-Forwarded-For` quando `WFM_TRUST_X_FORWARDED_FOR=True`, e então usa o último item (o acrescentado pelo proxy), nunca o primeiro (forjável).

**Concorrência.** Registro de ponto e mudança de status de tarefa usam `select_for_update()` dentro de transação para evitar duplo clique/requisições simultâneas gerando estados inválidos. (No SQLite o bloqueio é no banco inteiro; no PostgreSQL é por linha.)

**Imutabilidade do log de ponto.** Garantida na aplicação: `RegistroPonto.save()` só insere, `delete()` e o QuerySet (`update`, `bulk_update`, `delete`) levantam `RegistroImutavel`, a FK de `Funcionario` é `PROTECT` e o admin é somente leitura. Isso **não** protege contra SQL direto. Para produção, reforce no PostgreSQL com um usuário de aplicação sem esses privilégios:

```sql
-- O usuário que roda as migrações é dono das tabelas; a aplicação usa outro usuário.
REVOKE UPDATE, DELETE, TRUNCATE ON ponto_registroponto FROM wfm_app;
GRANT SELECT, INSERT ON ponto_registroponto TO wfm_app;
```

**Leveza para terminais modestos.** Sem JavaScript, sem fontes ou CDNs externos; um único CSS (~6 KB). Formulários usam inputs HTML5 nativos (`date`, `datetime-local`). Listagens longas são paginadas. Padrão POST-redirect-GET em todas as ações.

**Banco.** PostgreSQL 16 é o alvo (docker-compose e CI); SQLite é só para início rápido e roda a mesma suíte de testes.

## Fluxo de uma requisição (registro de ponto)

```
Navegador ──POST /ponto/ {tipo=entrada}──▶ Gunicorn ──▶ middlewares (sessão, CSRF, auth)
   ──▶ views.meu_ponto  (@somente_funcionario → 403 para outros perfis)
   ──▶ RegistroForm valida só o "tipo"
   ──▶ services.registrar_ponto: trava o funcionário, confere alternância e terminal,
       cria RegistroPonto (hora = servidor)
   ◀── 302 redireciona para GET /ponto/ (mensagem de sucesso ou recusa)
```

## Evolução (Fase 2)

- Novas filiais: cadastrar `Filial`/`Setor`/`Terminal` e usuários; nenhuma mudança de código de núcleo.
- Perfil de "gerente regional" (vê várias filiais): ajustar `perfil_required` e os filtros `filial=...` para aceitar um conjunto de filiais.
- Proteção de força bruta no login (ex.: `django-axes`) e troca de senha obrigatória no 1º acesso.
- Exportação do log de horas para a folha (CSV) a partir de `ponto.services.resumo_frequencia`.
