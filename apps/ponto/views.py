"""Views do ponto: registro pelo funcionário (RS14) e consulta pelo gerente (RS09)."""
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.core.permissions import somente_funcionario, somente_gerente
from apps.core.utils import agora_local, ip_do_cliente, limites_do_dia, limites_periodo, paginar

from . import services
from .forms import LogPontoForm, RegistroForm
from .models import RegistroPonto, TipoRegistro


@somente_funcionario
def meu_ponto(request):
    """RS14: o funcionário registra entrada/saída. O horário é o do servidor."""
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Tipo de registro inválido.")
        else:
            try:
                registro = services.registrar_ponto(
                    request.user, form.cleaned_data["tipo"], ip_do_cliente(request))
            except services.PontoRecusado as erro:
                messages.error(request, str(erro))
            else:
                hora = timezone.localtime(registro.registrado_em)
                messages.success(request, f"{registro.get_tipo_display()} registrada às "
                                          f"{hora:%H:%M:%S} (horário do servidor).")
        return redirect("ponto:meu_ponto")  # padrão POST-redirect-GET: evita reenvio ao atualizar

    inicio, fim = limites_do_dia(agora_local().date())
    hoje = RegistroPonto.objects.filter(funcionario=request.user,
                                        registrado_em__gte=inicio, registrado_em__lt=fim)
    return render(request, "ponto/meu_ponto.html", {
        "registros_hoje": hoje.order_by("registrado_em"),
        "proximo": TipoRegistro(services.proximo_tipo(request.user)),
        "hora_servidor": agora_local(),
    })


@somente_gerente
def log(request):
    """RS09: log de ponto com frequência. Só o perfil Gerente (os demais recebem 403)."""
    filial = request.user.filial
    hoje = agora_local().date()
    # Datas ausentes na URL (1º acesso ou só ?page=N) assumem os últimos 7 dias.
    dados = request.GET.copy()
    dados.setdefault("data_inicial", (hoje - timedelta(days=7)).isoformat())
    dados.setdefault("data_final", hoje.isoformat())
    form = LogPontoForm(dados, filial=filial)

    contexto = {"form": form}
    if form.is_valid():
        inicio, fim = limites_periodo(form.cleaned_data["data_inicial"], form.cleaned_data["data_final"])
        registros = (RegistroPonto.objects
                     .filter(funcionario__filial=filial, registrado_em__gte=inicio, registrado_em__lt=fim)
                     .select_related("funcionario", "terminal"))
        if form.cleaned_data["funcionario"]:
            registros = registros.filter(funcionario=form.cleaned_data["funcionario"])

        pagina, qs = paginar(request, registros.order_by("-registrado_em", "-pk"), por_pagina=50)
        contexto.update({
            "pagina": pagina, "qs": qs,
            # A frequência usa ordem cronológica crescente para parear entrada/saída.
            "frequencia": services.resumo_frequencia(registros.order_by("registrado_em", "pk")),
        })
    return render(request, "ponto/log.html", contexto)
