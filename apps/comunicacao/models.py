"""Comunicados do gerente (RS08/RS15) e mensagens do funcionário ao gerente (RS16)."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

LIMITE_TEXTO = 500  # RS08: "até 500 caracteres"


class DestinoComunicado(models.TextChoices):
    FUNCIONARIO = "funcionario", "Um funcionário"
    SETOR = "setor", "Um setor"
    TODOS = "todos", "Todos os funcionários"


class ComunicadoQuerySet(models.QuerySet):
    def para(self, funcionario):
        """Comunicados visíveis a um funcionário (RS15): destinados a ele, ao seu setor
        ou a todos da sua filial."""
        return self.filter(
            Q(destino_tipo=DestinoComunicado.TODOS, filial_id=funcionario.filial_id)
            | Q(destino_tipo=DestinoComunicado.SETOR, setor_id=funcionario.setor_id)
            | Q(destino_tipo=DestinoComunicado.FUNCIONARIO, destinatario_id=funcionario.pk)
        )


class Comunicado(models.Model):
    filial = models.ForeignKey("core.Filial", on_delete=models.PROTECT, related_name="comunicados")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              related_name="comunicados_enviados")
    destino_tipo = models.CharField("destino", max_length=15, choices=DestinoComunicado.choices)
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True,
                                     blank=True, related_name="comunicados_recebidos")
    setor = models.ForeignKey("core.Setor", on_delete=models.CASCADE, null=True, blank=True,
                              related_name="comunicados")
    texto = models.CharField("mensagem", max_length=LIMITE_TEXTO)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)
    # True para notificações geradas pelo sistema (ex.: remanejamento, RS17).
    automatico = models.BooleanField(default=False)

    objects = ComunicadoQuerySet.as_manager()

    class Meta:
        ordering = ["-criado_em", "-id"]

    def __str__(self):
        return f"{self.get_destino_tipo_display()}: {self.texto[:40]}"

    @property
    def destino_descricao(self) -> str:
        if self.destino_tipo == DestinoComunicado.SETOR and self.setor:
            return f"Setor {self.setor.nome}"
        if self.destino_tipo == DestinoComunicado.FUNCIONARIO and self.destinatario:
            return self.destinatario.nome
        return "Todos"


class LeituraComunicado(models.Model):
    """Marca que um funcionário já abriu o comunicado (contador de não lidos no menu)."""

    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE, related_name="leituras")
    funcionario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="+")
    lido_em = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["comunicado", "funcionario"], name="leitura_unica"),
        ]


class TipoMensagem(models.TextChoices):
    DUVIDA = "duvida", "Dúvida"
    TROCA_TURNO = "troca_turno", "Solicitação de troca de turno"
    OUTRO = "outro", "Outro assunto"


class Mensagem(models.Model):
    """RS16: mensagem curta do funcionário ao gerente."""

    remetente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                  related_name="mensagens_enviadas")
    tipo = models.CharField("assunto", max_length=15, choices=TipoMensagem.choices,
                            default=TipoMensagem.DUVIDA)
    texto = models.CharField("mensagem", max_length=LIMITE_TEXTO)
    criada_em = models.DateTimeField(default=timezone.now, editable=False)
    lida = models.BooleanField(default=False)

    class Meta:
        ordering = ["-criada_em", "-id"]

    def __str__(self):
        return f"{self.remetente}: {self.texto[:40]}"
