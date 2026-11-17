"""Contadores exibidos no menu: comunicados não lidos (funcionário) e mensagens novas (gerente)."""
from apps.core.perfis import Perfil

from .models import Comunicado, Mensagem


def nao_lidos(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated or usuario.filial_id is None:
        return {}
    if usuario.perfil == Perfil.FUNCIONARIO:
        total = Comunicado.objects.para(usuario).exclude(leituras__funcionario=usuario).count()
    elif usuario.perfil == Perfil.GERENTE:
        total = Mensagem.objects.filter(remetente__filial_id=usuario.filial_id, lida=False).count()
    else:
        return {}
    return {"badge_nao_lidos": total}
