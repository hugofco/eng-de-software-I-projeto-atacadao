"""Formulários de login, cadastro/edição (RS01/RS02) e filtro da listagem."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from apps.core.models import Setor

from apps.core.widgets import FORMATOS_DATA, DataInput

from .models import Funcionario
from .validators import somente_digitos


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="CPF ou matrícula", max_length=30,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Senha", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    error_messages = {
        "invalid_login": "CPF/matrícula ou senha incorretos, ou acesso desativado.",
        "inactive": "Este acesso está desativado.",
    }


class FuncionarioForm(forms.ModelForm):
    """RS01/RS02. As restrições (CPF válido e único, nome, idade ≥ 16, listas
    pré-definidas) estão nos validadores/FKs do modelo; aqui só adaptamos a entrada."""

    # Campo declarado para aceitar CPF formatado (14 chars) e normalizar para dígitos.
    cpf = forms.CharField(label="CPF", max_length=14,
                          help_text="Somente números ou no formato 000.000.000-00.")
    data_nascimento = forms.DateField(label="Data de nascimento", widget=DataInput(),
                                      input_formats=FORMATOS_DATA)

    class Meta:
        model = Funcionario
        fields = ["nome", "cpf", "data_nascimento", "perfil", "cargo", "setor", "turno",
                  "carga_horaria_semanal"]

    def __init__(self, *args, filial, ator=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Setor limitado à filial do gerente; cargo/setor são obrigatórios (RS01).
        self.fields["setor"].queryset = Setor.objects.filter(filial=filial)
        self.fields["setor"].required = True
        self.fields["cargo"].required = True
        # Ninguém altera o próprio perfil (evita o gerente se rebaixar por engano).
        if ator is not None and self.instance.pk == ator.pk:
            self.fields["perfil"].disabled = True

    def clean_cpf(self):
        return somente_digitos(self.cleaned_data["cpf"])


class FuncionarioCadastroForm(FuncionarioForm):
    """Cadastro: acrescenta a senha inicial (opcional)."""

    senha_inicial = forms.CharField(
        label="Senha inicial", required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Opcional. Se vazio, o sistema gera uma senha temporária e a exibe uma única vez.",
    )

    def clean_senha_inicial(self):
        senha = self.cleaned_data.get("senha_inicial")
        if senha:
            validate_password(senha)
        return senha


class FiltroFuncionarioForm(forms.Form):
    q = forms.CharField(label="Busca", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Nome, matrícula ou CPF"}))
    setor = forms.ModelChoiceField(label="Setor", queryset=Setor.objects.none(), required=False,
                                   empty_label="Todos")
    status = forms.ChoiceField(label="Status", required=False,
                               choices=[("", "Todos"), ("ativo", "Ativos"), ("inativo", "Inativos")])

    def __init__(self, *args, filial, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["setor"].queryset = Setor.objects.filter(filial=filial)
