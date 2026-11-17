"""
Widgets HTML5 nativos (sem JavaScript) para data e data/hora.

Usam o formato ISO exigido por <input type="date"> / "datetime-local", que não
coincide com o formato pt-BR padrão do Django (dd/mm/aaaa).
"""
from django import forms

FORMATOS_DATA = ["%Y-%m-%d", "%d/%m/%Y"]
FORMATOS_DATA_HORA = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"]


class DataInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


class DataHoraInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%dT%H:%M")


def campo_data(label: str, **kwargs) -> forms.DateField:
    return forms.DateField(
        label=label, widget=DataInput(), input_formats=FORMATOS_DATA, **kwargs
    )


def campo_data_hora(label: str, **kwargs) -> forms.DateTimeField:
    return forms.DateTimeField(
        label=label, widget=DataHoraInput(), input_formats=FORMATOS_DATA_HORA, **kwargs
    )
