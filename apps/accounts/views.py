"""Views de funcionários (RS01–RS03). Acesso restrito ao perfil Gerente."""
import re

from django.contrib import messages
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from apps.core.permissions import somente_gerente
from apps.core.utils import paginar

from . import services
from .forms import (FiltroFuncionarioForm, FuncionarioCadastroForm, FuncionarioForm,
                    LoginForm)
from .models import Funcionario
from .validators import somente_digitos


class EntrarView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class TrocarSenhaView(PasswordChangeView):
    template_name = "accounts/trocar_senha.html"
    success_url = reverse_lazy("core:home")


def _funcionario_da_filial(request, pk):
    """Busca restrita à filial do gerente (404 para registros de outras filiais)."""
    return get_object_or_404(Funcionario, pk=pk, filial=request.user.filial)


@somente_gerente
def lista(request):
    filial = request.user.filial
    funcionarios = (Funcionario.objects.filter(filial=filial)
                    .select_related("setor", "cargo").order_by("nome"))
    filtro = FiltroFuncionarioForm(request.GET or None, filial=filial)
    if filtro.is_valid():
        dados = filtro.cleaned_data
        if dados["q"]:
            termo = dados["q"]
            criterio = Q(nome__icontains=termo) | Q(matricula__icontains=termo)
            # Só trata o termo como CPF se ele for composto apenas por dígitos e
            # pontuação; do contrário "Pessoa F2" casaria todo CPF contendo "2".
            if re.fullmatch(r"[\d.\-\s]+", termo):
                criterio |= Q(cpf__icontains=somente_digitos(termo))
            funcionarios = funcionarios.filter(criterio)
        if dados["setor"]:
            funcionarios = funcionarios.filter(setor=dados["setor"])
        if dados["status"]:
            funcionarios = funcionarios.filter(is_active=dados["status"] == "ativo")
    pagina, qs = paginar(request, funcionarios)
    return render(request, "accounts/funcionario_lista.html",
                  {"filtro": filtro, "pagina": pagina, "qs": qs})


@somente_gerente
def novo(request):
    form = FuncionarioCadastroForm(request.POST or None, filial=request.user.filial)
    if request.method == "POST" and form.is_valid():
        funcionario = form.save(commit=False)
        senha = services.cadastrar_funcionario(
            funcionario, ator=request.user, senha=form.cleaned_data["senha_inicial"])
        texto = f"Funcionário cadastrado. Matrícula: {funcionario.matricula}."
        if senha:
            texto += f" Senha temporária: {senha} (anote agora: não será exibida novamente)."
        messages.success(request, texto)
        return redirect("accounts:lista")
    return render(request, "accounts/funcionario_form.html",
                  {"form": form, "titulo": "Novo funcionário", "funcionario": None})


@somente_gerente
def editar(request, pk):
    funcionario = _funcionario_da_filial(request, pk)
    # O snapshot precisa ser tirado ANTES de construir o form: a validação do
    # ModelForm já altera a instância em memória.
    antes = services.snapshot(funcionario)
    titulo = f"Editar: {funcionario.nome}"  # antes de o form alterar a instância
    form = FuncionarioForm(request.POST or None, instance=funcionario,
                           filial=request.user.filial, ator=request.user)
    if request.method == "POST" and form.is_valid():
        mudancas = services.salvar_edicao(form.save(commit=False), antes, request.user)
        messages.success(request, "Dados atualizados." if mudancas else "Nenhuma alteração a salvar.")
        return redirect("accounts:lista")
    return render(request, "accounts/funcionario_form.html", {
        "form": form, "titulo": titulo, "funcionario": funcionario,
        "alteracoes": funcionario.alteracoes.select_related("alterado_por")[:10],
    })


@somente_gerente
@require_POST
def alterar_status(request, pk):
    funcionario = _funcionario_da_filial(request, pk)
    if funcionario.pk == request.user.pk:
        messages.error(request, "Você não pode desativar o próprio acesso.")
    else:
        ativo = services.alternar_status(funcionario, request.user)
        messages.success(request, f"{funcionario.nome} agora está {'ativo' if ativo else 'inativo'}.")
    return redirect("accounts:lista")
