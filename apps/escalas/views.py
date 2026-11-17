"""Views de escalas (gerente e funcionário), ocorrências e remanejamento."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Funcionario
from apps.core.perfis import Perfil
from apps.core.permissions import somente_funcionario, somente_gerente
from apps.core.turnos import Turno

from . import services
from .forms import EscalaSemanaForm, OcorrenciaForm, RemanejamentoForm
from .models import DiaSemana, Ocorrencia


def _grade(escalas) -> list[str]:
    """Lista de 7 rótulos (segunda..domingo): nome do turno ou '—' (folga)."""
    por_dia = {e.dia_semana: Turno(e.turno).label for e in escalas}
    return [por_dia.get(dia, "—") for dia in range(7)]


@somente_gerente
def visao_geral(request):
    """Quadro semanal da equipe (RU03): uma linha por funcionário, uma coluna por dia."""
    equipe = (Funcionario.objects
              .filter(filial=request.user.filial, perfil=Perfil.FUNCIONARIO, is_active=True)
              .prefetch_related("escalas").order_by("nome"))
    linhas = []
    for f in equipe:
        escalas = list(f.escalas.all())
        linhas.append({"funcionario": f, "dias": _grade(escalas),
                       "horas": services.horas_semanais({e.dia_semana: e.turno for e in escalas})})
    return render(request, "escalas/visao_geral.html",
                  {"linhas": linhas, "dias": [d.label for d in DiaSemana]})


@somente_gerente
def editar(request, pk):
    """RS06/RS07: define ou edita a escala semanal de um funcionário."""
    funcionario = get_object_or_404(Funcionario, pk=pk, filial=request.user.filial,
                                    perfil=Perfil.FUNCIONARIO, is_active=True)
    form = EscalaSemanaForm(request.POST or None, funcionario=funcionario)
    if request.method == "POST" and form.is_valid():
        services.salvar_escala(funcionario, form.turnos(), request.user)
        messages.success(request, f"Escala de {funcionario.nome} salva.")
        return redirect("escalas:visao_geral")
    ultima = funcionario.escalas.order_by("-atualizada_em").select_related("atualizada_por").first()
    return render(request, "escalas/editar.html",
                  {"form": form, "funcionario": funcionario, "ultima": ultima})


@somente_funcionario
def minha(request):
    """RS12: o funcionário vê SOMENTE a própria escala (id vem da sessão, nunca da URL)."""
    escalas = list(request.user.escalas.all())
    dias = [{"nome": d.label, "turno": t} for d, t in zip(DiaSemana, _grade(escalas), strict=True)]
    horas = services.horas_semanais({e.dia_semana: e.turno for e in escalas})
    return render(request, "escalas/minha.html", {"dias": dias, "horas": horas})


@somente_gerente
def ocorrencias(request):
    """RS11: registro e listagem de ausências, atrasos e trocas de turno."""
    filial = request.user.filial
    inicial = {"funcionario": request.GET.get("funcionario")} if request.method == "GET" else None
    form = OcorrenciaForm(request.POST or None, filial=filial, initial=inicial)
    if request.method == "POST" and form.is_valid():
        ocorrencia = form.save(commit=False)
        ocorrencia.registrada_por = request.user
        ocorrencia.save()
        messages.success(request, "Ocorrência registrada.")
        return redirect("escalas:ocorrencias")
    recentes = (Ocorrencia.objects.filter(funcionario__filial=filial)
                .select_related("funcionario", "registrada_por")[:50])
    return render(request, "escalas/ocorrencias.html", {"form": form, "ocorrencias": recentes})


@somente_gerente
def remanejar(request):
    """RS17: remanejamento imediato com notificação automática."""
    form = RemanejamentoForm(request.POST or None, filial=request.user.filial)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        services.remanejar(dados["funcionario"], dados["setor_destino"], dados["funcao"], request.user)
        messages.success(request, f"{dados['funcionario'].nome} remanejado(a) e notificado(a).")
        return redirect("escalas:remanejar")
    return render(request, "escalas/remanejar.html",
                  {"form": form, "ha_disponiveis": form.disponiveis.exists()})
