"""Admin do Django: apoio técnico. O cadastro de funcionários é feito pelo sistema
(que gera matrícula e senha corretamente), por isso aqui não há botão 'adicionar'."""
from django.contrib import admin

from .models import AlteracaoFuncionario, Funcionario


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ("matricula", "nome", "perfil", "setor", "filial", "is_active")
    list_filter = ("perfil", "filial", "setor", "is_active")
    search_fields = ("nome", "matricula", "cpf")
    exclude = ("password",)  # senhas só mudam pelo fluxo do sistema
    readonly_fields = ("last_login", "criado_em", "atualizado_em", "atualizado_por")

    def has_add_permission(self, request):
        return False


@admin.register(AlteracaoFuncionario)
class AlteracaoFuncionarioAdmin(admin.ModelAdmin):
    list_display = ("em", "funcionario", "campo", "valor_anterior", "valor_novo", "alterado_por")
    # Trilha de auditoria: somente leitura.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
