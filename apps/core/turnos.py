"""
Turnos de trabalho e suas janelas de horário.

O documento fala em turnos "manhã, tarde ou noite" (RS01, RS06) mas não define
os horários. PREMISSA do protótipo: três janelas de 6 horas, ajustáveis aqui
(fonte única de verdade para escala, carga horária e disponibilidade do RS17).
"""
from datetime import time

from django.db import models


class Turno(models.TextChoices):
    MANHA = "manha", "Manhã"
    TARDE = "tarde", "Tarde"
    NOITE = "noite", "Noite"


# (hora de início, hora de fim) em horário local. 24 = meia-noite do dia seguinte.
JANELAS = {
    "manha": (6, 12),
    "tarde": (12, 18),
    "noite": (18, 24),
}

# Descanso mínimo entre o fim de um turno e o início do seguinte (CLT, art. 66).
INTERVALO_MINIMO_HORAS = 11


def horas_do_turno(turno: str) -> int:
    """Duração do turno em horas (usada no cálculo da carga horária semanal)."""
    inicio, fim = JANELAS[turno]
    return fim - inicio


def turno_em(hora: time) -> str | None:
    """Turno vigente em dada hora local; None fora de qualquer janela (00h-06h)."""
    for turno, (inicio, fim) in JANELAS.items():
        if inicio <= hora.hour < fim:
            return turno
    return None


def descanso_entre(turno_anterior: str, turno_seguinte: str) -> int:
    """Horas de descanso entre o fim de `turno_anterior` (dia D) e o início de
    `turno_seguinte` (dia D+1)."""
    return (24 - JANELAS[turno_anterior][1]) + JANELAS[turno_seguinte][0]
