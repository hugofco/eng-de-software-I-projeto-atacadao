"""Regras do ponto: registro (RS14) e consolidação de frequência (RS09)."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Funcionario
from apps.core.models import Terminal

from .models import RegistroPonto, TipoRegistro


class PontoRecusado(Exception):
    """Registro rejeitado por regra de negócio; a mensagem é exibida ao funcionário."""


def proximo_tipo(funcionario) -> str:
    """Tipo esperado agora: alterna entrada/saída a partir do último registro.

    A alternância é global (não por dia) porque turnos noturnos atravessam a meia-noite.
    """
    ultimo = RegistroPonto.objects.filter(funcionario=funcionario).first()  # ordering: mais recente
    return TipoRegistro.SAIDA if ultimo and ultimo.tipo == TipoRegistro.ENTRADA else TipoRegistro.ENTRADA


def registrar_ponto(funcionario, tipo: str, ip: str | None) -> RegistroPonto:
    """Cria o registro de ponto com o relógio do servidor (RS14).

    O horário NÃO é parâmetro: vem de `timezone.now()` (default do campo). O
    cliente só informa o tipo. Regras:
    - Entrada e saída devem se alternar.
    - Com WFM_ENFORCE_TERMINAL_IP, o IP deve ser de um Terminal ativo da filial.
    """
    with transaction.atomic():
        # Trava o funcionário: dois cliques simultâneos não geram duas entradas.
        Funcionario.objects.select_for_update().get(pk=funcionario.pk)

        esperado = proximo_tipo(funcionario)
        if tipo != esperado:
            raise PontoRecusado(
                f"Você precisa registrar {TipoRegistro(esperado).label.upper()} agora "
                f"(o último registro foi {'uma entrada' if esperado == TipoRegistro.SAIDA else 'uma saída'}).")

        terminal = None
        if ip:
            terminal = Terminal.objects.filter(ip_address=ip, ativo=True,
                                               filial_id=funcionario.filial_id).first()
        if settings.WFM_ENFORCE_TERMINAL_IP and terminal is None:
            raise PontoRecusado("O ponto só pode ser registrado a partir de um terminal da loja.")

        return RegistroPonto.objects.create(funcionario=funcionario, tipo=tipo,
                                            ip_origem=ip, terminal=terminal)


def _formatar_duracao(total: timedelta) -> str:
    horas, resto = divmod(int(total.total_seconds()), 3600)
    return f"{horas}h{resto // 60:02d}min"


def resumo_frequencia(registros) -> list[dict]:
    """Consolida registros em frequência por funcionário (RS09: 'entrada, saída e frequência').

    `registros` deve estar em ordem CRONOLÓGICA crescente e com `funcionario`
    carregado. Pareia cada entrada com a saída seguinte; uma entrada sem saída
    fica como 'em aberto' e não soma horas.
    """
    resumo, entradas_abertas = {}, {}
    for r in registros:
        item = resumo.setdefault(r.funcionario_id, {
            "funcionario": r.funcionario, "dias": set(), "total": timedelta(0), "em_aberto": False})
        if r.tipo == TipoRegistro.ENTRADA:
            entradas_abertas[r.funcionario_id] = r.registrado_em
            item["dias"].add(timezone.localtime(r.registrado_em).date())
        else:
            inicio = entradas_abertas.pop(r.funcionario_id, None)
            if inicio is not None:
                item["total"] += r.registrado_em - inicio
    for funcionario_id in entradas_abertas:
        resumo[funcionario_id]["em_aberto"] = True

    linhas = sorted(resumo.values(), key=lambda i: i["funcionario"].nome)
    for item in linhas:
        item["dias_trabalhados"] = len(item["dias"])
        item["horas"] = _formatar_duracao(item["total"])
    return linhas
