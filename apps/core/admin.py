from django.contrib import admin

from .models import Cargo, Filial, Setor, Terminal


@admin.register(Filial)
class FilialAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativa")


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("nome", "filial", "areas", "ramal")
    list_filter = ("filial",)
    search_fields = ("nome", "areas")


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    search_fields = ("nome",)


@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ("nome", "ip_address", "filial", "ativo")
    list_filter = ("filial", "ativo")
