"""Regras de escala (RS06/RS07), disponibilidade e remanejamento imediato (RS17)."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Funcionario
from apps.comunicacao.models import Comunicado, DestinoComunicado
from apps.core.perfis import Perfil
from apps.core.turnos import (INTERVALO_MINIMO_HORAS, Turno, descanso_entre, horas_do_turno,
                              turno_em)
from apps.core.utils import agora_local

from .models import DiaSemana, Escala, Ocorrencia, Remanejamento, TipoOcorrencia


def horas_semanais(turnos: dict) -> int:
    """Soma de horas de uma escala {dia: turno|''}."""
    return sum(horas_do_turno(t) for t in turnos.values() if t)


def validar_escala(funcionario, turnos: dict) -> list[str]:
    """Valida uma escala semanal proposta {dia(0-6): turno ou ''}. Devolve os erros.

    Regras:
    1. A carga semanal não pode ultrapassar o limite contratual (RS06/RS07).
    2. Não pode haver "horários incompatíveis": respeita-se o descanso mínimo de
       11 h entre o fim de um turno e o início do seguinte (ex.: noite → manhã
       do dia seguinte são só 6 h). Considera a virada Domingo → Segunda.
    3. Sobreposição no mesmo dia é impossível: há no máximo um turno por dia.
    """
    erros = []
    horas = horas_semanais(turnos)
    if horas > funcionario.carga_horaria_semanal:
        erros.append(f"A escala soma {horas} h semanais e excede o limite contratual de "
                     f"{funcionario.carga_horaria_semanal} h.")

    for dia in range(7):
        proximo = (dia + 1) % 7
        atual, seguinte = turnos.get(dia), turnos.get(proximo)
        if atual and seguinte:
            descanso = descanso_entre(atual, seguinte)
            if descanso < INTERVALO_MINIMO_HORAS:
                erros.append(
                    f"{DiaSemana(dia).label} ({Turno(atual).label}) seguido de "
                    f"{DiaSemana(proximo).label} ({Turno(seguinte).label}) deixa só {descanso} h "
                    f"de descanso; o mínimo é {INTERVALO_MINIMO_HORAS} h.")
    return erros


@transaction.atomic
def salvar_escala(funcionario, turnos: dict, ator) -> None:
    """Grava a escala semanal, registrando data e autor apenas dos dias que mudaram."""
    agora = timezone.now()
    existentes = {e.dia_semana: e for e in Escala.objects.filter(funcionario=funcionario)}
    for dia in range(7):
        turno, atual = turnos.get(dia, ""), existentes.get(dia)
        if turno and atual is None:
            Escala.objects.create(funcionario=funcionario, dia_semana=dia, turno=turno,
                                  atualizada_em=agora, atualizada_por=ator)
        elif turno and atual.turno != turno:
            atual.turno, atual.atualizada_em, atual.atualizada_por = turno, agora, ator
            atual.save(update_fields=["turno", "atualizada_em", "atualizada_por"])
        elif not turno and atual is not None:
            atual.delete()


def funcionarios_disponiveis(filial, agora=None):
    """Funcionários que podem ser remanejados AGORA (RS17).

    Disponível = ativo, perfil Funcionário, escalado hoje no turno vigente e sem
    ausência registrada hoje. Fora das janelas de turno (00h–06h), ninguém.
    """
    agora = agora or agora_local()
    turno = turno_em(agora.time())
    if turno is None:
        return Funcionario.objects.none()

    escalados = Escala.objects.filter(dia_semana=agora.weekday(), turno=turno).values("funcionario_id")
    ausentes = Ocorrencia.objects.filter(tipo=TipoOcorrencia.AUSENCIA,
                                         data=agora.date()).values("funcionario_id")
    return (Funcionario.objects
            .filter(filial=filial, perfil=Perfil.FUNCIONARIO, is_active=True, pk__in=escalados)
            .exclude(pk__in=ausentes)
            .select_related("setor").order_by("nome"))


@transaction.atomic
def remanejar(funcionario, setor_destino, funcao: str, ator) -> Remanejamento:
    """Registra o remanejamento e notifica o funcionário com o horário atual (RS17)."""
    agora = timezone.now()
    remanejamento = Remanejamento.objects.create(
        funcionario=funcionario, setor_origem=funcionario.setor, setor_destino=setor_destino,
        funcao=funcao, iniciado_em=agora, criado_por=ator)

    local = timezone.localtime(agora)
    Comunicado.objects.create(
        filial=ator.filial, autor=ator, automatico=True,
        destino_tipo=DestinoComunicado.FUNCIONARIO, destinatario=funcionario,
        texto=(f"Remanejamento imediato: você foi designado(a) para “{funcao}” no setor "
               f"{setor_destino.nome}, com início às {local:%H:%M} de {local:%d/%m/%Y}."))
    return remanejamento
