"""
Regras de negócio de cadastro/edição/desativação de funcionários (RS01–RS03).

As views ficam finas e chamam estas funções; assim a regra é testável sem HTTP.
"""
import secrets
import uuid

from django.db import transaction
from django.utils import timezone

from .models import AlteracaoFuncionario

# Campos cuja mudança é registrada na trilha de auditoria (RS02).
CAMPOS_AUDITADOS = ["nome", "cpf", "data_nascimento", "perfil", "cargo", "setor", "turno",
                    "carga_horaria_semanal"]

# Alfabeto sem caracteres ambíguos (0/O, 1/l/I) para senhas temporárias digitadas à mão.
_ALFABETO_SENHA = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gerar_senha_temporaria(tamanho: int = 10) -> str:
    return "".join(secrets.choice(_ALFABETO_SENHA) for _ in range(tamanho))


@transaction.atomic
def cadastrar_funcionario(funcionario, ator, senha=None):
    """Persiste um funcionário novo (RS01) e devolve a senha temporária gerada.

    - A filial é herdada do gerente que cadastra.
    - A matrícula é sequencial (derivada da chave primária). Como a PK só existe
      após o INSERT, grava-se um valor provisório único e corrige-se em seguida,
      tudo na mesma transação.
    - Se `senha` não for informada, gera-se uma temporária; ela é devolvida UMA
      vez para o gerente repassar ao funcionário. Retorna None se o gerente
      definiu a senha manualmente.
    """
    senha_gerada = None if senha else gerar_senha_temporaria()
    funcionario.filial = ator.filial
    funcionario.matricula = f"tmp-{uuid.uuid4().hex[:12]}"
    funcionario.set_password(senha or senha_gerada)
    funcionario.save()
    funcionario.matricula = f"{funcionario.pk:05d}"
    funcionario.save(update_fields=["matricula"])
    return senha_gerada


def snapshot(funcionario) -> dict:
    """Valores atuais dos campos auditados, como texto (para comparar antes/depois)."""
    return {campo: str(getattr(funcionario, campo)) for campo in CAMPOS_AUDITADOS}


@transaction.atomic
def salvar_edicao(funcionario, antes: dict, ator) -> dict:
    """Salva a edição (RS02) registrando data/usuário e a trilha de campos alterados.

    `antes` é o snapshot() tirado ANTES de o formulário alterar a instância.
    Se nada mudou, não grava nada. Retorna {campo: (antes, depois)}.
    """
    depois = snapshot(funcionario)
    mudancas = {c: (antes[c], depois[c]) for c in CAMPOS_AUDITADOS if antes[c] != depois[c]}
    if not mudancas:
        return {}

    agora = timezone.now()
    funcionario.atualizado_em = agora
    funcionario.atualizado_por = ator
    funcionario.save()
    AlteracaoFuncionario.objects.bulk_create([
        AlteracaoFuncionario(funcionario=funcionario, alterado_por=ator, em=agora,
                             campo=campo, valor_anterior=a, valor_novo=d)
        for campo, (a, d) in mudancas.items()
    ])
    return mudancas


@transaction.atomic
def alternar_status(funcionario, ator) -> bool:
    """Ativa/desativa um funcionário (RS03). Devolve o novo valor de `is_active`.

    Desativar remove o acesso, mas preserva tarefas e ponto (FKs com PROTECT).
    """
    agora = timezone.now()
    anterior = funcionario.is_active
    funcionario.is_active = not anterior
    funcionario.atualizado_em = agora
    funcionario.atualizado_por = ator
    funcionario.save(update_fields=["is_active", "atualizado_em", "atualizado_por"])
    AlteracaoFuncionario.objects.create(
        funcionario=funcionario, alterado_por=ator, em=agora, campo="status",
        valor_anterior="ativo" if anterior else "inativo",
        valor_novo="inativo" if anterior else "ativo",
    )
    return funcionario.is_active
