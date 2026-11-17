"""Views de tarefas: gestão (gerente), minhas tarefas (funcionário) e painel."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.perfis import Perfil
from apps.core.permissions import somente_funcionario, somente_gerente
from apps.core.utils import paginar

from . import services
from .forms import FiltroTarefaForm, TarefaForm
from .models import StatusTarefa, Tarefa


@somente_gerente
def lista(request):
    """RS05: consulta de tarefas com filtros por setor, funcionário e status."""
    filial = request.user.filial
    tarefas = (Tarefa.objects.filter(setor__filial=filial)
               .select_related("setor").prefetch_related("responsaveis")
               .order_by("prazo", "pk"))
    filtro = FiltroTarefaForm(request.GET or None, filial=filial)
    if filtro.is_valid():
        dados = filtro.cleaned_data
        if dados["setor"]:
            tarefas = tarefas.filter(setor=dados["setor"])
        if dados["funcionario"]:
            tarefas = tarefas.filter(responsaveis=dados["funcionario"])
        if dados["status"]:
            tarefas = tarefas.filter(status=dados["status"])
    pagina, qs = paginar(request, tarefas)
    return render(request, "tarefas/lista.html", {"filtro": filtro, "pagina": pagina, "qs": qs})


@somente_gerente
def nova(request):
    """RS04: criação de tarefa. Fica visível imediatamente na lista e para os responsáveis."""
    form = TarefaForm(request.POST or None, filial=request.user.filial)
    if request.method == "POST" and form.is_valid():
        tarefa = form.save(commit=False)
        tarefa.criada_por = request.user
        tarefa.save()
        tarefa.responsaveis.set(form.responsaveis_efetivos())
        messages.success(request, "Tarefa criada e atribuída.")
        return redirect("tarefas:lista")
    return render(request, "tarefas/form.html", {"form": form})


@somente_gerente
def painel(request):
    """RS10: contagem por setor das tarefas do dia."""
    return render(request, "tarefas/painel.html", services.painel_por_setor(request.user.filial))


@somente_funcionario
def minhas(request):
    """RU10: tarefas atribuídas ao funcionário logado (abertas por padrão)."""
    ver = request.GET.get("ver", "abertas")
    tarefas = request.user.tarefas_atribuidas.select_related("setor").order_by("prazo", "pk")
    if ver == "encerradas":
        tarefas = tarefas.filter(status__in=[StatusTarefa.CONCLUIDA, StatusTarefa.CANCELADA])
    else:
        ver = "abertas"
        tarefas = tarefas.filter(status__in=[StatusTarefa.PENDENTE, StatusTarefa.EM_ANDAMENTO])
    return render(request, "tarefas/minhas.html", {"tarefas": tarefas, "ver": ver})


@login_required
@require_POST
def alterar_status(request, pk):
    """Endpoint único de mudança de status; as permissões vivem em services.alterar_status."""
    usuario = request.user
    if usuario.perfil not in (Perfil.GERENTE, Perfil.FUNCIONARIO):
        raise PermissionDenied
    tarefa = get_object_or_404(Tarefa, pk=pk, setor__filial=usuario.filial)
    try:
        services.alterar_status(tarefa.pk, request.POST.get("novo", ""), usuario)
    except services.TransicaoInvalida as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Status atualizado.")
    return redirect("tarefas:lista" if usuario.perfil == Perfil.GERENTE else "tarefas:minhas")
