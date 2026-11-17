"""
Validadores das restrições do RS01 (cadastro de funcionário).

As funções puras (`cpf_valido`, `somente_digitos`) não dependem de banco e são
reutilizadas pelo seed e pelos testes.
"""
import re
from datetime import date

from django.core.exceptions import ValidationError
from django.utils import timezone

IDADE_MINIMA = 16  # RS01: "idade mínima de 16 anos"


def somente_digitos(valor: str | None) -> str:
    """Remove tudo que não for dígito (aceita CPF como 000.000.000-00)."""
    return re.sub(r"\D", "", valor or "")


def digitos_verificadores(base9: str) -> str:
    """Calcula os 2 dígitos verificadores de um CPF a partir dos 9 primeiros."""
    digitos = [int(c) for c in base9]
    for tamanho in (9, 10):
        # pesos: 10..2 para o 1º dígito, 11..2 para o 2º
        soma = sum(d * (tamanho + 1 - i) for i, d in enumerate(digitos[:tamanho]))
        digitos.append((soma * 10 % 11) % 10)
    return "".join(str(d) for d in digitos[9:])


def cpf_valido(cpf: str | None) -> bool:
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:  # rejeita 111.111.111-11 etc.
        return False
    return digitos_verificadores(cpf[:9]) == cpf[9:]


def validate_cpf(valor: str) -> None:
    if not cpf_valido(valor):
        raise ValidationError("CPF inválido.", code="cpf_invalido")


def validate_nome(valor: str) -> None:
    """RS01: o nome 'não pode iniciar com números ou caracteres especiais'.

    O primeiro caractere deve ser uma letra (inclui acentuadas).
    """
    if not re.match(r"[^\W\d_]", (valor or "").strip()):
        raise ValidationError(
            "O nome deve começar com uma letra (sem números ou caracteres especiais).",
            code="nome_invalido",
        )


def calcular_idade(nascimento: date, hoje: date) -> int:
    return hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))


def validate_nascimento(valor: date) -> None:
    """RS01: data anterior à atual e idade mínima de 16 anos."""
    hoje = timezone.localdate()
    if valor >= hoje:
        raise ValidationError("A data de nascimento deve ser anterior à data atual.", code="nascimento_futuro")
    if calcular_idade(valor, hoje) < IDADE_MINIMA:
        raise ValidationError(f"Idade mínima de {IDADE_MINIMA} anos.", code="menor_de_idade")
