"""Escala semanal (RS06/RS07/RS12), ocorrências (RS11) e remanejamentos (RS17)."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.turnos import Turno


class DiaSemana(models.IntegerChoices):
    # Mesma numeração de datetime.weekday(): segunda = 0 ... domingo = 6.
    SEGUNDA = 0, "Segunda-feira"
    TERCA = 1, "Terça-feira"
    QUARTA = 2, "Quarta-feira"
    QUINTA = 3, "Quinta-feira"
    SEXTA = 4, "Sexta-feira"
    SABADO = 5, "Sábado"
    DOMINGO = 6, "Domingo"


class Escala(models.Model):
    """Turno de um funcionário em um dia da semana. Sem linha = folga.

    A restrição de unicidade (funcionário, dia) já impede dois turnos sobrepostos
    no mesmo dia; as demais regras (carga horária, descanso) estão em services.py.
    """

    funcionario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="escalas")
    dia_semana = models.PositiveSmallIntegerField("dia da semana", choices=DiaSemana.choices)
    turno = models.CharField("turno", max_length=10, choices=Turno.choices)
    # RS06: "registrando a data da alteração".
    atualizada_em = models.DateTimeField(default=timezone.now, editable=False)
    atualizada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, related_name="+", editable=False)

    class Meta:
        ordering = ["funcionario", "dia_semana"]
        constraints = [
            models.UniqueConstraint(fields=["funcionario", "dia_semana"], name="escala_unica_por_dia"),
        ]

    def __str__(self):
        return f"{self.funcionario} — {self.get_dia_semana_display()}: {self.get_turno_display()}"


class TipoOcorrencia(models.TextChoices):
    AUSENCIA = "ausencia", "Ausência"
    ATRASO = "atraso", "Atraso"
    TROCA_TURNO = "troca_turno", "Troca de turno"


class Ocorrencia(models.Model):
    """RS11: ausência, atraso ou troca de turno, com data e observação."""

    funcionario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="ocorrencias")
    tipo = models.CharField("tipo", max_length=15, choices=TipoOcorrencia.choices)
    data = models.DateField("data")
    observacao = models.CharField("observação", max_length=300)
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, related_name="+", editable=False)
    registrada_em = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-data", "-id"]

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.funcionario} em {self.data}"


class Remanejamento(models.Model):
    """RS17: funcionário designado para cobrir uma função imediata.

    Não altera o setor de cadastro do funcionário: é uma designação pontual.
    """

    funcionario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="remanejamentos")
    setor_origem = models.ForeignKey("core.Setor", on_delete=models.PROTECT, related_name="+")
    setor_destino = models.ForeignKey("core.Setor", on_delete=models.PROTECT, related_name="+")
    funcao = models.CharField("função a cobrir", max_length=120)
    # RS17: "horário de início ... preenchido automaticamente com o horário atual".
    iniciado_em = models.DateTimeField(default=timezone.now, editable=False)
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, related_name="+", editable=False)

    class Meta:
        ordering = ["-iniciado_em"]

    def __str__(self):
        return f"{self.funcionario} → {self.setor_destino} ({self.funcao})"
