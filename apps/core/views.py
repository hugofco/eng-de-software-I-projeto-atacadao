"""Tela inicial por perfil e diretório do Comprador (RS18)."""
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render

from apps.accounts.models import Funcionario

from .models import Setor
from .perfis import Perfil
from .permissions import perfil_required
from .utils import agora_local


@login_required
def home(request):
    """Página inicial: cada perfil vê apenas o que lhe cabe (seção 3 do documento)."""
    usuario = request.user
    if usuario.perfil == Perfil.COMPRADOR:
        return redirect("core:diretorio")

    contexto = {}
    if usuario.filial_id:
        # Importações locais: a home é o ponto de composição entre módulos.
        if usuario.perfil == Perfil.GERENTE:
            from apps.tarefas.services import painel_por_setor
            contexto["painel"] = painel_por_setor(usuario.filial)
        elif usuario.perfil == Perfil.FUNCIONARIO:
            from apps.escalas.models import Escala
            from apps.ponto.models import RegistroPonto
            from apps.tarefas.models import StatusTarefa

            contexto["tarefas_abertas"] = usuario.tarefas_atribuidas.filter(
                status__in=[StatusTarefa.PENDENTE, StatusTarefa.EM_ANDAMENTO]).count()
            contexto["escala_hoje"] = Escala.objects.filter(
                funcionario=usuario, dia_semana=agora_local().weekday()).first()
            contexto["ultimo_ponto"] = RegistroPonto.objects.filter(funcionario=usuario).first()
    return render(request, "core/home.html", contexto)


@perfil_required(Perfil.COMPRADOR, Perfil.GERENTE)
def diretorio(request):
    """RS18: o comprador encontra o setor (e quem atende) por produto ou área.

    Exibe SOMENTE nome do funcionário e setor, sem CPF, cargo, escala ou qualquer
    dado de gestão. Por isso a consulta usa values_list com apenas essas colunas.
    """
    termo = request.GET.get("q", "").strip()
    setores = Setor.objects.filter(filial=request.user.filial)
    if termo:
        setores = setores.filter(Q(nome__icontains=termo) | Q(areas__icontains=termo))
    setores = setores.order_by("nome")

    equipes = defaultdict(list)
    nomes = (Funcionario.objects
             .filter(is_active=True, perfil=Perfil.FUNCIONARIO, setor__in=setores)
             .order_by("nome").values_list("nome", "setor_id"))
    for nome, setor_id in nomes:
        equipes[setor_id].append(nome)

    linhas = [{"setor": s, "funcionarios": equipes.get(s.pk, [])} for s in setores]
    return render(request, "core/diretorio.html", {"linhas": linhas, "termo": termo})
