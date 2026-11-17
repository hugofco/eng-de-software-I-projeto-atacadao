from django import forms

from apps.accounts.models import Funcionario
from apps.core.perfis import Perfil
from apps.core.widgets import campo_data

from .models import TipoRegistro


class RegistroForm(forms.Form):
    """O funcionário informa APENAS o tipo. Não existe campo de data/hora (RS14)."""

    tipo = forms.ChoiceField(choices=TipoRegistro.choices)


class LogPontoForm(forms.Form):
    """RS09: período (data inicial não pode ser posterior à final) e funcionário opcional."""

    data_inicial = campo_data("De")
    data_final = campo_data("Até")
    funcionario = forms.ModelChoiceField(label="Funcionário", queryset=Funcionario.objects.none(),
                                         required=False, empty_label="Todos")

    def __init__(self, *args, filial, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(
            filial=filial, perfil=Perfil.FUNCIONARIO).order_by("nome")

    def clean(self):
        dados = super().clean()
        inicial, final = dados.get("data_inicial"), dados.get("data_final")
        if inicial and final and inicial > final:
            raise forms.ValidationError("A data inicial não pode ser posterior à data final.")
        return dados
