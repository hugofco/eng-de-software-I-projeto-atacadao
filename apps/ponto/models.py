"""
Log de Ponto: "registro imutável de entrada e saída associado ao relógio do
servidor, base para conformidade trabalhista" (seção 1.3).

A imutabilidade é garantida na camada de aplicação: o modelo e o QuerySet
recusam UPDATE e DELETE, e o admin é somente leitura. PARA PRODUÇÃO, recomenda-se
reforçar no banco (REVOKE UPDATE/DELETE ou trigger no PostgreSQL) — ver docs/arquitetura.md.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class RegistroImutavel(Exception):
    """Tentativa de alterar ou apagar um registro de ponto."""


class TipoRegistro(models.TextChoices):
    ENTRADA = "entrada", "Entrada"
    SAIDA = "saida", "Saída"


class RegistroPontoQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RegistroImutavel("Registros de ponto não podem ser alterados.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise RegistroImutavel("Registros de ponto não podem ser alterados.")

    def delete(self):
        raise RegistroImutavel("Registros de ponto não podem ser apagados.")


class RegistroPonto(models.Model):
    # PROTECT: não é possível apagar um funcionário que tenha ponto (RS03).
    funcionario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="registros_ponto")
    tipo = models.CharField("tipo", max_length=10, choices=TipoRegistro.choices)
    # RS14: data/hora do SERVIDOR (UTC no banco). editable=False: nenhum formulário
    # ou admin consegue receber esse valor do usuário.
    registrado_em = models.DateTimeField("registrado em", default=timezone.now,
                                         editable=False, db_index=True)
    ip_origem = models.GenericIPAddressField("IP de origem", null=True, blank=True)
    terminal = models.ForeignKey("core.Terminal", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="registros")

    objects = RegistroPontoQuerySet.as_manager()

    class Meta:
        verbose_name = "registro de ponto"
        verbose_name_plural = "registros de ponto"
        ordering = ["-registrado_em", "-id"]

    def __str__(self):
        return f"{self.funcionario} — {self.get_tipo_display()} em {self.registrado_em:%d/%m/%Y %H:%M:%S}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RegistroImutavel("Registros de ponto não podem ser alterados.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroImutavel("Registros de ponto não podem ser apagados.")
