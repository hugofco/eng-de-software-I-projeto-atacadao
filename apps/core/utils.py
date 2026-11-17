"""Utilitários compartilhados entre os módulos (sem regra de negócio)."""
import ipaddress
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.paginator import Paginator
from django.utils import timezone


def agora_local() -> datetime:
    """Data/hora atual do SERVIDOR no fuso configurado (RS14: nunca do cliente).

    Centralizado aqui para que os testes possam substituir o relógio.
    """
    return timezone.localtime()


def _inicio_do_dia(dia) -> datetime:
    return timezone.make_aware(datetime.combine(dia, time.min))


def limites_do_dia(dia) -> tuple[datetime, datetime]:
    """Intervalo [início, fim) de um dia local, como datetimes com fuso."""
    return _inicio_do_dia(dia), _inicio_do_dia(dia + timedelta(days=1))


def limites_periodo(data_inicial, data_final) -> tuple[datetime, datetime]:
    """Intervalo [início, fim) cobrindo de data_inicial até o fim de data_final."""
    return _inicio_do_dia(data_inicial), _inicio_do_dia(data_final + timedelta(days=1))


def ip_do_cliente(request) -> str | None:
    """IP de origem da requisição, ou None se ausente/inválido.

    Por padrão usa REMOTE_ADDR. Com WFM_TRUST_X_FORWARDED_FOR=True (apenas atrás
    de proxy confiável) usa o ÚLTIMO item de X-Forwarded-For, que é o que o nosso
    proxy acrescentou; os itens anteriores podem ter sido forjados pelo cliente.
    """
    ip = request.META.get("REMOTE_ADDR", "")
    if settings.WFM_TRUST_X_FORWARDED_FOR:
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if encaminhado:
            ip = encaminhado.split(",")[-1].strip()
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


def paginar(request, itens, por_pagina: int = 25):
    """Pagina uma lista/queryset (ORDENADO). Retorna (página, querystring sem 'page')."""
    pagina = Paginator(itens, por_pagina).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return pagina, params.urlencode()
