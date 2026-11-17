# Requisitos: rastreabilidade, premissas e inconsistências

Fonte: *Plataforma de Gestão de Força de Trabalho para Atacadões* (v1.0, outubro/2026).

## 1. Matriz de rastreabilidade (RS → código → teste)

| RS | Atende | Funcionalidade | Onde está o código | Testes |
|----|--------|----------------|--------------------|--------|
| RS01 | RU01 | Cadastro de funcionário (CPF válido e único, nome, idade ≥ 16, listas, turno) | `accounts/validators.py`, `forms.py`, `services.cadastrar_funcionario`, `views.novo` | `accounts.tests.ValidadoresTests`, `CadastroTests` |
| RS02 | RU01 | Edição com última alteração (data + usuário) e trilha | `accounts/services.salvar_edicao`, `views.editar`, `AlteracaoFuncionario` | `accounts.tests.EdicaoTests` |
| RS03 | RU01 | Desativação sem apagar histórico | `accounts/services.alternar_status`, `backends.py` (bloqueia inativos), FKs `PROTECT` | `accounts.tests.DesativacaoTests` |
| RS04 | RU02 | Criação de tarefa (título, descrição, setor, prazo, responsáveis) | `tarefas/forms.TarefaForm`, `views.nova` | `tarefas.tests.CriacaoTests` |
| RS05 | RU02 | Consulta com filtros (setor, funcionário, status) | `tarefas/views.lista`, `FiltroTarefaForm` | `tarefas.tests.ConsultaTests` |
| RS06/RS07 | RU03 | Definição/edição de escala, limite contratual, data da alteração | `escalas/services.validar_escala`, `salvar_escala`, `views.editar` | `escalas.tests.ValidarEscalaTests`, `EdicaoDeEscalaTests` |
| RS08 | RU04 | Comunicado a funcionário, setor ou todos (≤ 500 caracteres) | `comunicacao/forms.ComunicadoForm`, `views.enviar` | `comunicacao.tests.EnvioDeComunicadoTests` |
| RS09 | RU05 | Log de ponto só para gerente; período válido; frequência | `ponto/views.log`, `services.resumo_frequencia`, `core/permissions.py` | `ponto.tests.ConsultaLogTests`, `ResumoFrequenciaTests`, `core.tests.AcessoPorPerfilTests` |
| RS10 | RU06 | Painel de tarefas do dia por setor | `tarefas/services.painel_por_setor`, `views.painel` | `tarefas.tests.PainelTests` |
| RS11 | RU07 | Ocorrências (ausência, atraso, troca de turno) | `escalas/models.Ocorrencia`, `views.ocorrencias` | `escalas.tests.OcorrenciaTests` |
| RS12 | RU09 | Funcionário consulta a própria escala (id da sessão) | `escalas/views.minha` | `escalas.tests.MinhaEscalaTests` |
| RS13 | RU10 | Funcionário altera status só das próprias tarefas; data de conclusão automática | `tarefas/services.alterar_status` | `tarefas.tests.AtualizacaoPeloFuncionarioTests` |
| RS14 | RU11 | Registro de ponto com relógio do servidor | `ponto/services.registrar_ponto`, `models.RegistroPonto` | `ponto.tests.RegistroTests`, `TerminalTests`, `ImutabilidadeTests` |
| RS15 | RU12* | Funcionário lê comunicados (dele, do setor, de todos) | `comunicacao/models.ComunicadoQuerySet.para`, `views.meus_comunicados` | `comunicacao.tests.LeituraDeComunicadosTests` |
| RS16 | RU13* | Funcionário envia mensagem ao gerente | `comunicacao/views.nova_mensagem`, `caixa_de_entrada` | `comunicacao.tests.MensagemAoGerenteTests` |
| RS17 | RU08* | Remanejamento imediato com notificação automática | `escalas/services.funcionarios_disponiveis`, `remanejar` | `escalas.tests.RemanejamentoTests` |
| RS18 | RU14 | Comprador consulta setor/área, só nome e setor | `core/views.diretorio` | `core.tests.DiretorioTests` |

\* Ver inconsistência 1 abaixo.

## 2. Inconsistências encontradas no documento original

Todas foram resolvidas a favor do **texto descritivo** de cada requisito; a rastreabilidade acima já reflete isso.

1. **Referências a RU trocadas nos RS finais.** O texto diz "RS15 (RU11)", "RS16 (RU12)", "RS17 (RU13)", mas pelo conteúdo: RS15 (consultar comunicados) atende **RU12**; RS16 (mensagem ao gerente) atende **RU13**; RS17 (remanejamento) atende **RU08**. A matriz da seção 5 do documento também lista RS14 e RS15 na mesma coluna (RU11).
2. **Diagrama 7.1 contradiz o resto do documento.** Mostra DRF, Serializers, Celery, Redis, WSS e CORS, mas o próprio texto exige renderização server-side "sem JS externo", monolito simples e "Previsão de Demanda" não consta em nenhum requisito. O protótipo **não** implementa essas peças; o diagrama corrigido está em `diagramas/01-arquitetura.puml`.
3. **Diagrama 7.3 não compila em PlantUML**: `rectangle "..."` com a chave `{` na linha seguinte e um comentário quebrado em duas linhas que faz `Direita) RU09 <-- funcionario` virar código. Além disso liga o Gerente a RU10, que é do Funcionário. Versão corrigida: `diagramas/03-casos-de-uso.puml`.
4. **Estados da tarefa.** RS05 lista "pendente, em execução ou concluída"; o diagrama 7.2 acrescenta **Cancelada** e a transição "pausar". Implementado conforme o diagrama.
5. **NTP.** A seção 2.2 diz que todo registro deve buscar o timestamp "do servidor NTP central". Uma aplicação Django usa o relógio do sistema operacional (`timezone.now()`); manter esse relógio sincronizado via NTP é responsabilidade da infraestrutura (chrony/systemd-timesyncd). O código garante o essencial: **o cliente nunca informa a hora**.
6. **Janelas de turno e "horário incompatível"** não são definidas (ver premissas).

## 3. Premissas adotadas

| # | Premissa | Onde mudar |
|---|----------|-----------|
| 1 | Turnos de 6 h: manhã 06–12, tarde 12–18, noite 18–24. Fora disso (00–06 h) ninguém está "disponível no turno". | `core/turnos.py` |
| 2 | "Sobreposição de horários incompatíveis com a carga horária" (RS06/RS07) = (a) soma semanal ≤ limite contratual do funcionário e (b) descanso mínimo de 11 h entre turnos (CLT, art. 66), inclusive domingo → segunda. Um turno por dia impede sobreposição no mesmo dia. | `escalas/services.validar_escala` |
| 3 | Limite contratual padrão 36 h/semana (máx. 44 h, CLT), editável por funcionário. | `accounts/models.py` |
| 4 | Matrícula sequencial gerada pelo sistema; senha inicial informada pelo gerente ou gerada e exibida uma única vez. | `accounts/services.py` |
| 5 | "Tarefas do dia" (RS10) = tarefas com **prazo** na data local de hoje, exceto canceladas; coluna extra "atrasadas" mostra abertas com prazo vencido de qualquer dia. | `tarefas/services.painel_por_setor` |
| 6 | Tarefa sem responsável marcado é atribuída a toda a equipe ativa do setor (distribuição por setor, seção 2.3). | `tarefas/forms.responsaveis_efetivos` |
| 7 | Funcionário só inicia, conclui ou pausa; gerente só cancela. Não se conclui direto de "pendente" (segue o diagrama 7.2). | `tarefas/services.py` |
| 8 | Disponível para remanejamento (RS17) = ativo, perfil Funcionário, escalado hoje no turno vigente e sem **ausência** registrada hoje. Não altera o setor de cadastro. | `escalas/services.funcionarios_disponiveis` |
| 9 | Só o perfil Funcionário registra ponto (RU11). Entrada e saída devem se alternar; a alternância é global (turno noturno cruza a meia-noite). | `ponto/services.registrar_ponto` |
| 10 | Verificação de IP de terminal é opcional (`WFM_ENFORCE_TERMINAL_IP`), desligada por padrão para a demonstração. | `.env`, `config/settings.py` |
| 11 | O log de ponto é imutável na camada de aplicação (modelo, QuerySet e admin). Para produção, reforçar no banco (ver `arquitetura.md`). | `ponto/models.py` |
| 12 | O Gerente também acessa o diretório (RS18), por ser somente nome/setor/contato. | `core/views.diretorio` |

## 4. Fora do escopo do protótipo

- Correção de ponto pelo gerente com trilha de auditoria (citada na seção 2.2, sem RS correspondente).
- Exportação de horas para folha (seção 1.2, sem RS).
- Edição de tarefa já criada (só criação, consulta e cancelamento).
- Troca obrigatória de senha no primeiro acesso e limitação de tentativas de login.
- Interface para cadastrar filiais, setores, cargos e terminais (use o `/admin/`).
- Recuperação de senha por e-mail (os funcionários não têm e-mail corporativo, seção 2.4).
