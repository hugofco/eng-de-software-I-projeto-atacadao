"""Views de comunicação: envio (gerente, RS08), leitura (funcionário, RS15), mensagens (RS16)."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import paginar
from apps.core.permissions import somente_funcionario, somente_gerente

from .forms import ComunicadoForm, MensagemForm
from .models import Comunicado, DestinoComunicado, LeituraComunicado, Mensagem


@somente_gerente
def enviar(request):
    """RS08: envia comunicado a um funcionário, a um setor ou a todos."""
    filial = request.user.filial
    form = ComunicadoForm(request.POST or None, filial=filial)
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        destino = dados["destino"]
        Comunicado.objects.create(
            filial=filial, autor=request.user, destino_tipo=destino, texto=dados["texto"],
            setor=dados["setor"] if destino == DestinoComunicado.SETOR else None,
            destinatario=dados["funcionario"] if destino == DestinoComunicado.FUNCIONARIO else None,
        )
        messages.success(request, "Comunicado enviado.")
        return redirect("comunicacao:enviar")
    enviados = (Comunicado.objects.filter(filial=filial, automatico=False)
                .select_related("setor", "destinatario", "autor")[:20])
    return render(request, "comunicacao/enviar.html", {"form": form, "enviados": enviados})


@somente_funcionario
def meus_comunicados(request):
    """RS15: comunicados destinados ao funcionário, ao seu setor ou a todos."""
    usuario = request.user
    comunicados = Comunicado.objects.para(usuario).select_related("autor", "setor")
    pagina, qs = paginar(request, comunicados, por_pagina=20)

    itens = list(pagina)
    ids = [c.pk for c in itens]
    ja_lidos = set(LeituraComunicado.objects.filter(funcionario=usuario, comunicado_id__in=ids)
                   .values_list("comunicado_id", flat=True))
    for c in itens:
        c.novo = c.pk not in ja_lidos
    # Abrir a lista marca os exibidos como lidos (o "novo" já foi calculado acima).
    LeituraComunicado.objects.bulk_create(
        [LeituraComunicado(comunicado_id=i, funcionario=usuario) for i in ids if i not in ja_lidos],
        ignore_conflicts=True)
    return render(request, "comunicacao/meus_comunicados.html",
                  {"comunicados": itens, "pagina": pagina, "qs": qs})


@somente_funcionario
def nova_mensagem(request):
    """RS16: o funcionário envia mensagem curta ao gerente."""
    form = MensagemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        mensagem = form.save(commit=False)
        mensagem.remetente = request.user
        mensagem.save()
        messages.success(request, "Mensagem enviada ao gerente.")
        return redirect("comunicacao:nova_mensagem")
    enviadas = Mensagem.objects.filter(remetente=request.user)[:20]
    return render(request, "comunicacao/nova_mensagem.html", {"form": form, "enviadas": enviadas})


@somente_gerente
def caixa_de_entrada(request):
    """Mensagens recebidas dos funcionários (RU13), não lidas primeiro."""
    mensagens = (Mensagem.objects.filter(remetente__filial=request.user.filial)
                 .select_related("remetente", "remetente__setor").order_by("lida", "-criada_em"))
    pagina, qs = paginar(request, mensagens, por_pagina=20)
    return render(request, "comunicacao/caixa.html", {"pagina": pagina, "qs": qs})


@somente_gerente
@require_POST
def marcar_lida(request, pk):
    mensagem = get_object_or_404(Mensagem, pk=pk, remetente__filial=request.user.filial)
    mensagem.lida = True
    mensagem.save(update_fields=["lida"])
    return redirect("comunicacao:caixa")
