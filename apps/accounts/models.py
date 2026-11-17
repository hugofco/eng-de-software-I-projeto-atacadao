"""
Modelo de usuário do sistema: o próprio Funcionário.

Decisões:
- Usuário customizado (AbstractBaseUser) com a MATRÍCULA como USERNAME_FIELD e
  login também por CPF (ver backends.py): "muitos trabalhadores do varejo não
  possuem e-mail corporativo" (seção 2.4).
- `is_active` é o 'status ativo/inativo' do RS03: desativar remove o acesso mas
  NÃO apaga o histórico (FKs de tarefas/ponto usam PROTECT).
- O CPF é armazenado somente com dígitos, para unicidade consistente.
"""
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.perfis import Perfil
from apps.core.turnos import Turno

from .validators import validate_cpf, validate_nascimento, validate_nome


class FuncionarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, matricula, password=None, **campos):
        """Cria um usuário comum (perfil Funcionário, se não informado)."""
        if not matricula:
            raise ValueError("A matrícula é obrigatória.")
        campos.setdefault("perfil", Perfil.FUNCIONARIO)
        usuario = self.model(matricula=matricula, **campos)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, matricula, password=None, **campos):
        """Superusuário: apenas para o /admin/ (não tem filial, não usa o sistema)."""
        campos.setdefault("is_staff", True)
        campos.setdefault("is_superuser", True)
        campos.setdefault("perfil", Perfil.GERENTE)
        return self.create_user(matricula, password, **campos)


class Funcionario(AbstractBaseUser, PermissionsMixin):
    matricula = models.CharField("matrícula", max_length=20, unique=True)
    nome = models.CharField("nome", max_length=150, validators=[validate_nome])
    cpf = models.CharField(
        "CPF", max_length=11, unique=True, validators=[validate_cpf],
        error_messages={"unique": "Já existe um funcionário cadastrado com este CPF."},
    )
    data_nascimento = models.DateField("data de nascimento", validators=[validate_nascimento])

    perfil = models.CharField("perfil de acesso", max_length=15, choices=Perfil.choices,
                              default=Perfil.FUNCIONARIO)
    # FKs anuláveis só para permitir o superusuário do /admin/; o formulário de
    # cadastro (RS01) torna cargo, setor e turno obrigatórios.
    filial = models.ForeignKey("core.Filial", on_delete=models.PROTECT, null=True, blank=True,
                               related_name="funcionarios")
    setor = models.ForeignKey("core.Setor", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="funcionarios")
    cargo = models.ForeignKey("core.Cargo", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="funcionarios")
    turno = models.CharField("turno", max_length=10, choices=Turno.choices, default=Turno.MANHA)
    # Limite contratual usado para validar a escala (RS06/RS07). Máx. 44 h (CLT, art. 7º XIII).
    carga_horaria_semanal = models.PositiveSmallIntegerField(
        "carga horária semanal (h)", default=36,
        validators=[MinValueValidator(1), MaxValueValidator(44)],
    )

    is_active = models.BooleanField("ativo", default=True)
    is_staff = models.BooleanField("acesso ao /admin/", default=False)

    criado_em = models.DateTimeField(default=timezone.now, editable=False)
    # RS02: "histórico da última alteração realizada, incluindo data e usuário responsável"
    atualizado_em = models.DateTimeField("última alteração em", null=True, blank=True, editable=False)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", editable=False, verbose_name="última alteração por",
    )

    objects = FuncionarioManager()

    USERNAME_FIELD = "matricula"
    REQUIRED_FIELDS = ["nome", "cpf", "data_nascimento"]

    class Meta:
        verbose_name = "funcionário"
        verbose_name_plural = "funcionários"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.matricula})"

    def get_full_name(self):
        return self.nome

    def get_short_name(self):
        return self.nome.split()[0] if self.nome else self.matricula

    @property
    def cpf_formatado(self) -> str:
        c = self.cpf
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c

    @property
    def eh_gerente(self) -> bool:
        return self.perfil == Perfil.GERENTE

    @property
    def eh_funcionario(self) -> bool:
        return self.perfil == Perfil.FUNCIONARIO

    @property
    def eh_comprador(self) -> bool:
        return self.perfil == Perfil.COMPRADOR


class AlteracaoFuncionario(models.Model):
    """Trilha de auditoria das edições (quem, quando, o quê).

    Complementa o RS02 (que exige apenas a última alteração) e segue a lição da
    TOTVS na seção 2.2: correções deixam trilha de auditoria.
    """

    funcionario = models.ForeignKey(Funcionario, on_delete=models.CASCADE, related_name="alteracoes")
    alterado_por = models.ForeignKey(Funcionario, on_delete=models.SET_NULL, null=True, related_name="+")
    em = models.DateTimeField(default=timezone.now, editable=False)
    campo = models.CharField(max_length=40)
    valor_anterior = models.CharField(max_length=200, blank=True)
    valor_novo = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-em", "-id"]

    def __str__(self):
        return f"{self.funcionario}: {self.campo} ({self.valor_anterior} → {self.valor_novo})"
