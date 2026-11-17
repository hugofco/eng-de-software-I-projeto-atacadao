"""Perfis de acesso (atores da seção 1.3 do documento)."""
from django.db import models


class Perfil(models.TextChoices):
    GERENTE = "gerente", "Gerente"
    FUNCIONARIO = "funcionario", "Funcionário"
    COMPRADOR = "comprador", "Comprador"
