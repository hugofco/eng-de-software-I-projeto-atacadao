from django.contrib import admin

from .models import RegistroPonto


@admin.register(RegistroPonto)
class RegistroPontoAdmin(admin.ModelAdmin):
    """Somente leitura: o log de ponto é imutável (seção 1.3)."""

    list_display = ("registrado_em", "funcionario", "tipo", "ip_origem", "terminal")
    list_filter = ("tipo", "terminal")
    search_fields = ("funcionario__nome", "funcionario__matricula")
    date_hierarchy = "registrado_em"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
