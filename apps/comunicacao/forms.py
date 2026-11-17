from django import forms

from apps.accounts.models import Funcionario
from apps.core.models import Setor
from apps.core.perfis import Perfil

from .models import LIMITE_TEXTO, DestinoComunicado, Mensagem


class ComunicadoForm(forms.Form):
    """RS08: destinatário (funcionário, setor ou todos) e texto de até 500 caracteres."""

    destino = forms.ChoiceField(label="Enviar para", choices=DestinoComunicado.choices,
                                widget=forms.RadioSelect, initial=DestinoComunicado.TODOS)
    setor = forms.ModelChoiceField(label="Setor", queryset=Setor.objects.none(), required=False)
    funcionario = forms.ModelChoiceField(label="Funcionário", queryset=Funcionario.objects.none(),
                                         required=False)
    texto = forms.CharField(label="Mensagem", max_length=LIMITE_TEXTO,
                            widget=forms.Textarea(attrs={"rows": 4}),
                            help_text=f"Até {LIMITE_TEXTO} caracteres.")

    def __init__(self, *args, filial, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["setor"].queryset = Setor.objects.filter(filial=filial)
        self.fields["funcionario"].queryset = Funcionario.objects.filter(
            filial=filial, perfil=Perfil.FUNCIONARIO, is_active=True).order_by("nome")

    def clean(self):
        dados = super().clean()
        destino = dados.get("destino")
        if destino == DestinoComunicado.SETOR and not dados.get("setor"):
            self.add_error("setor", "Selecione o setor de destino.")
        if destino == DestinoComunicado.FUNCIONARIO and not dados.get("funcionario"):
            self.add_error("funcionario", "Selecione o funcionário de destino.")
        return dados


class MensagemForm(forms.ModelForm):
    """RS16: mensagem curta ao gerente."""

    class Meta:
        model = Mensagem
        fields = ["tipo", "texto"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 4})}
        labels = {"tipo": "Assunto", "texto": "Mensagem"}
