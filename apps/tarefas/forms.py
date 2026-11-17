"""Formulários de tarefas (RS04) e filtros de consulta (RS05)."""
from django import forms
from django.utils import timezone

from apps.accounts.models import Funcionario
from apps.core.models import Setor
from apps.core.perfis import Perfil
from apps.core.widgets import campo_data_hora

from .models import StatusTarefa, Tarefa


def _equipe_ativa(filial):
    return Funcionario.objects.filter(filial=filial, perfil=Perfil.FUNCIONARIO,
                                      is_active=True).order_by("nome")


class TarefaForm(forms.ModelForm):
    prazo = campo_data_hora("Prazo")
    responsaveis = forms.ModelMultipleChoiceField(
        label="Responsáveis", queryset=Funcionario.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Se nenhum for marcado, a tarefa é atribuída a toda a equipe ativa do setor "
                  "(distribuição por setor, como no varejo).",
    )

    class Meta:
        model = Tarefa
        fields = ["titulo", "descricao", "setor", "prazo", "responsaveis"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, filial, **kwargs):
        super().__init__(*args, **kwargs)
        self.filial = filial
        self.fields["setor"].queryset = Setor.objects.filter(filial=filial)
        self.fields["responsaveis"].queryset = _equipe_ativa(filial)

    def clean_prazo(self):
        prazo = self.cleaned_data["prazo"]
        if prazo < timezone.now():
            raise forms.ValidationError("O prazo não pode estar no passado.")
        return prazo

    def clean(self):
        dados = super().clean()
        setor, marcados = dados.get("setor"), dados.get("responsaveis")
        if setor and not marcados and not _equipe_ativa(self.filial).filter(setor=setor).exists():
            self.add_error("responsaveis",
                           "Este setor não tem funcionários ativos: selecione os responsáveis.")
        return dados

    def responsaveis_efetivos(self):
        """Responsáveis marcados ou, se nenhum, toda a equipe ativa do setor."""
        marcados = self.cleaned_data["responsaveis"]
        if marcados:
            return marcados
        return _equipe_ativa(self.filial).filter(setor=self.cleaned_data["setor"])


class FiltroTarefaForm(forms.Form):
    """RS05: filtros opcionais por setor, funcionário e status."""

    setor = forms.ModelChoiceField(label="Setor", queryset=Setor.objects.none(), required=False,
                                   empty_label="Todos")
    funcionario = forms.ModelChoiceField(label="Funcionário", queryset=Funcionario.objects.none(),
                                         required=False, empty_label="Todos")
    status = forms.ChoiceField(label="Status", required=False,
                               choices=[("", "Todos")] + list(StatusTarefa.choices))

    def __init__(self, *args, filial, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["setor"].queryset = Setor.objects.filter(filial=filial)
        self.fields["funcionario"].queryset = _equipe_ativa(filial)
