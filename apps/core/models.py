"""
Estrutura organizacional: Filial > Setor, além de Cargo e Terminal.

"Modelagem lógica que suporte agrupamento por setores e filiais desde o dia 1"
(seção 2.4). O protótipo opera com UMA filial, mas todo dado de negócio
referencia a filial (direta ou via setor), então a Fase 2 não exige refatoração.
"""
from django.db import models


class Filial(models.Model):
    nome = models.CharField("nome", max_length=120, unique=True)
    ativa = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "filial"
        verbose_name_plural = "filiais"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Setor(models.Model):
    """Setor/corredor da loja. É também a unidade de distribuição de tarefas
    (Reflexis, seção 2.3) e de comunicados (RS08)."""

    filial = models.ForeignKey(Filial, on_delete=models.PROTECT, related_name="setores")
    nome = models.CharField("nome", max_length=80)
    # Dados exibidos ao Comprador (RU14 / RS18): o que o setor atende e como contatá-lo.
    areas = models.CharField(
        "produtos/áreas atendidos", max_length=255, blank=True,
        help_text="Ex.: Bebidas, Laticínios, Congelados",
    )
    ramal = models.CharField("ramal/contato", max_length=20, blank=True)

    class Meta:
        verbose_name = "setor"
        verbose_name_plural = "setores"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["filial", "nome"], name="setor_unico_por_filial"),
        ]

    def __str__(self):
        return self.nome


class Cargo(models.Model):
    """Lista pré-definida de cargos (RS01: 'deve pertencer a uma lista pré-definida')."""

    nome = models.CharField("nome", max_length=80, unique=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Terminal(models.Model):
    """Computador físico da loja, com IP fixo (seção 1.3).

    Quando WFM_ENFORCE_TERMINAL_IP=True, o ponto só é aceito de IPs cadastrados aqui.
    """

    filial = models.ForeignKey(Filial, on_delete=models.PROTECT, related_name="terminais")
    nome = models.CharField("nome", max_length=80)
    ip_address = models.GenericIPAddressField("IP fixo", unique=True)
    ativo = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.ip_address})"
