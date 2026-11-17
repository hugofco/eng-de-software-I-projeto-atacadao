"""Formulários de escala, ocorrência e remanejamento."""
from django import forms

from apps.accounts.models import Funcionario
from apps.core.models import Setor
from apps.core.perfis import Perfil
from apps.core.turnos import Turno
from apps.core.widgets import campo_data

from . import services
from .models import DiaSemana, Ocorrencia


class EscalaSemanaForm(forms.Form):
    """Grade com um campo por dia da semana ('Folga' ou um turno)."""

    def __init__(self, *args, funcionario, **kwargs):
        super().__init__(*args, **kwargs)
        self.funcionario = funcionario
        atuais = {e.dia_semana: e.turno for e in funcionario.escalas.all()}
        for dia, nome in DiaSemana.choices:
            self.fields[f"dia_{dia}"] = forms.ChoiceField(
                label=nome, required=False, initial=atuais.get(dia, ""),
                choices=[("", "Folga")] + list(Turno.choices))

    def turnos(self) -> dict:
        """{dia: turno ou ''} a partir dos dados já validados."""
        return {dia: self.cleaned_data.get(f"dia_{dia}", "") for dia in range(7)}

    def clean(self):
        dados = super().clean()
        if not self.errors:
            erros = services.validar_escala(self.funcionario, self.turnos())
            if erros:
                raise forms.ValidationError(erros)
        return dados


class OcorrenciaForm(forms.ModelForm):
    data = campo_data("Data")

    class Meta:
        model = Ocorrencia
        fields = ["funcionario", "tipo", "data", "observacao"]
        widgets = {"observacao": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, filial, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(
            filial=filial, perfil=Perfil.FUNCIONARIO, is_active=True).order_by("nome")


class RemanejamentoForm(forms.Form):
    funcionario = forms.ModelChoiceField(label="Funcionário disponível",
                                         queryset=Funcionario.objects.none())
    setor_destino = forms.ModelChoiceField(label="Setor a cobrir", queryset=Setor.objects.none())
    funcao = forms.CharField(label="Função a cobrir", max_length=120,
                             help_text="Ex.: caixa, reposição de bebidas, apoio no açougue.")

    def __init__(self, *args, filial, **kwargs):
        super().__init__(*args, **kwargs)
        # A lista é recalculada a cada requisição (e ao validar): quem deixou de
        # estar disponível entre abrir e enviar o formulário é rejeitado.
        self.disponiveis = services.funcionarios_disponiveis(filial)
        self.fields["funcionario"].queryset = self.disponiveis
        self.fields["funcionario"].label_from_instance = lambda f: f"{f.nome} — {f.setor}"
        self.fields["setor_destino"].queryset = Setor.objects.filter(filial=filial)
