"""
Fábrica de dados compartilhada pelos testes dos módulos.

Não é um módulo de testes (o nome não começa com "test"); apenas monta um cenário
mínimo: duas filiais, dois setores, um gerente, dois funcionários e um comprador.
"""
from datetime import date
from types import SimpleNamespace

from apps.accounts.models import Funcionario
from apps.accounts.validators import digitos_verificadores
from apps.core.models import Cargo, Filial, Setor
from apps.core.perfis import Perfil

SENHA = "senha-de-teste-123"


def gerar_cpf(n: int) -> str:
    """CPF válido e determinístico (11 dígitos) para o número `n`."""
    base = f"{100000000 + n * 7919:09d}"[:9]
    return base + digitos_verificadores(base)


def criar_usuario(matricula, n, filial, setor, cargo, perfil=Perfil.FUNCIONARIO, **extra):
    return Funcionario.objects.create_user(
        matricula=matricula, password=SENHA, nome=f"Pessoa {matricula}", cpf=gerar_cpf(n),
        data_nascimento=date(1990, 1, 1), perfil=perfil, filial=filial, setor=setor,
        cargo=cargo, **extra)


def criar_cenario() -> SimpleNamespace:
    """Cria e devolve o cenário-base dos testes."""
    filial = Filial.objects.create(nome="Loja A")
    outra_filial = Filial.objects.create(nome="Loja B")
    setor_a = Setor.objects.create(filial=filial, nome="Bebidas", areas="Cervejas, Refrigerantes")
    setor_b = Setor.objects.create(filial=filial, nome="Limpeza", areas="Produtos de limpeza")
    setor_outra = Setor.objects.create(filial=outra_filial, nome="Bebidas")
    cargo = Cargo.objects.create(nome="Repositor Especial")

    return SimpleNamespace(
        filial=filial, outra_filial=outra_filial,
        setor_a=setor_a, setor_b=setor_b, setor_outra=setor_outra, cargo=cargo,
        gerente=criar_usuario("G1", 1, filial, setor_a, cargo, Perfil.GERENTE, carga_horaria_semanal=44),
        func1=criar_usuario("F1", 2, filial, setor_a, cargo),
        func2=criar_usuario("F2", 3, filial, setor_b, cargo),
        comprador=criar_usuario("C1", 4, filial, setor_a, cargo, Perfil.COMPRADOR),
        # Funcionário de OUTRA filial: nunca deve aparecer para o gerente da Loja A.
        func_outra=criar_usuario("X1", 5, outra_filial, setor_outra, cargo),
    )
