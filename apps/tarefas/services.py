"""Regras de negócio das tarefas: transições de status (RS13) e painel (RS10)."""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.core.models import Setor
from apps.core.perfis import Perfil
from apps.core.utils import agora_local, limites_do_dia

from .models import StatusTarefa as S
from .models import Tarefa


class TransicaoInvalida(Exception):
    """Mudança de status não permitida pelo ciclo de vida da tarefa."""


# Máquina de estados do diagrama 7.2: {estado atual: estados alcançáveis}.
# Usa os VALORES (strings puras), que é o que vem do banco e dos formulários.
PENDENTE, EM_ANDAMENTO = S.PENDENTE.value, S.EM_ANDAMENTO.value
CONCLUIDA, CANCELADA = S.CONCLUIDA.value, S.CANCELADA.value

TRANSICOES = {
    PENDENTE: {EM_ANDAMENTO, CANCELADA},
    EM_ANDAMENTO: {CONCLUIDA, PENDENTE, CANCELADA},  # voltar a PENDENTE = "pausar"
    CONCLUIDA: set(),
    CANCELADA: set(),
}

# Quem pode levar a tarefa a cada estado (RS13 e diagrama 7.2).
FUNCIONARIO_PODE = {EM_ANDAMENTO, CONCLUIDA, PENDENTE}  # iniciar, concluir, pausar
GERENTE_PODE = {CANCELADA}                              # "gerente revoga"


@transaction.atomic
def alterar_status(tarefa_id: int, novo_status: str, ator) -> Tarefa:
    """Muda o status de uma tarefa aplicando as regras de permissão e de transição.

    - Funcionário: só tarefas atribuídas a ele (RS13) e só iniciar/concluir/pausar.
    - Gerente: só cancelar ("revogar").
    - Ao concluir, `concluida_em` recebe o relógio do SERVIDOR (RS13).

    Levanta PermissionDenied (→ HTTP 403) ou TransicaoInvalida (→ mensagem ao usuário).
    """
    # Trava a linha para que dois cliques simultâneos não corram em paralelo.
    tarefa = Tarefa.objects.select_for_update().get(pk=tarefa_id)

    if ator.perfil == Perfil.FUNCIONARIO:
        if not tarefa.responsaveis.filter(pk=ator.pk).exists():
            raise PermissionDenied("Tarefa atribuída a outro funcionário.")
        permitidos = FUNCIONARIO_PODE
    elif ator.perfil == Perfil.GERENTE:
        permitidos = GERENTE_PODE
    else:
        raise PermissionDenied

    if novo_status not in S.values:
        raise TransicaoInvalida("Status inválido.")
    if novo_status not in permitidos:
        raise PermissionDenied("Seu perfil não pode aplicar esta mudança de status.")
    if novo_status not in TRANSICOES[tarefa.status]:
        raise TransicaoInvalida(
            f"Não é possível passar de “{S(tarefa.status).label}” para “{S(novo_status).label}”.")

    tarefa.status = novo_status
    tarefa.concluida_em = timezone.now() if novo_status == CONCLUIDA else None
    tarefa.save(update_fields=["status", "concluida_em"])
    return tarefa


def painel_por_setor(filial, agora=None) -> dict:
    """Contagem de tarefas pendentes / em execução / concluídas por setor (RS10).

    Define-se "tarefas do dia" como as com PRAZO na data local atual. Como tarefas
    vencidas e não concluídas sumiriam do painel no dia seguinte, acrescenta-se a
    coluna "atrasadas" (abertas com prazo já vencido, de qualquer dia).
    """
    agora = agora or agora_local()
    inicio, fim = limites_do_dia(agora.date())

    colunas = (PENDENTE, EM_ANDAMENTO, CONCLUIDA, "atrasadas")
    linhas = {
        s.pk: {"setor": s, **{coluna: 0 for coluna in colunas}}
        for s in Setor.objects.filter(filial=filial).order_by("nome")
    }

    do_dia = (Tarefa.objects
              .filter(setor__filial=filial, prazo__gte=inicio, prazo__lt=fim)
              .exclude(status=CANCELADA)
              .values("setor_id", "status").annotate(total=Count("id")))
    for r in do_dia:
        linhas[r["setor_id"]][r["status"]] = r["total"]

    atrasadas = (Tarefa.objects
                 .filter(setor__filial=filial, prazo__lt=agora,
                         status__in=[PENDENTE, EM_ANDAMENTO])
                 .values("setor_id").annotate(total=Count("id")))
    for r in atrasadas:
        linhas[r["setor_id"]]["atrasadas"] = r["total"]

    lista = list(linhas.values())
    totais = {coluna: sum(linha[coluna] for linha in lista) for coluna in colunas}
    return {"linhas": lista, "totais": totais}
