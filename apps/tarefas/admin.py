from django.contrib import admin

from .models import Tarefa


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "setor", "status", "prazo", "concluida_em")
    list_filter = ("status", "setor")
    search_fields = ("titulo",)
    filter_horizontal = ("responsaveis",)
