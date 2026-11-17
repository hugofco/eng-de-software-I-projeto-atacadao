"""
Tarefas de chão de loja (RS04, RS05, RS13).

Status simples, como recomenda a seção 2.3 (Reflexis). O ciclo de vida segue a
máquina de estados do diagrama 7.2 (ver services.TRANSICOES).
"""
from django.conf import settings
from django.db import models


class StatusTarefa(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    CONCLUIDA = "concluida", "Concluída"
    CANCELADA = "cancelada", "Cancelada"


class Tarefa(models.Model):
    titulo = models.CharField("título", max_length=120)
    descricao = models.TextField("descrição", blank=True)
    setor = models.ForeignKey("core.Setor", on_delete=models.PROTECT, related_name="tarefas")
    prazo = models.DateTimeField("prazo")
    status = models.CharField("status", max_length=15, choices=StatusTarefa.choices,
                              default=StatusTarefa.PENDENTE, db_index=True)
    responsaveis = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="tarefas_atribuidas",
                                          blank=True, verbose_name="responsáveis")
    criada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   related_name="+", editable=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    # RS13: preenchida automaticamente pelo sistema ao concluir.
    concluida_em = models.DateTimeField("concluída em", null=True, blank=True, editable=False)

    def __str__(self):
        return self.titulo

    @property
    def aberta(self) -> bool:
        return self.status in (StatusTarefa.PENDENTE, StatusTarefa.EM_ANDAMENTO)
