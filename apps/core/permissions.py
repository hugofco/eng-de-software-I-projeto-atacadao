"""
Controle de acesso por perfil (hierarquia da seção 3 do documento).

Todas as views protegidas usam estes decoradores. Negar acesso levanta
PermissionDenied, que o Django converte em HTTP 403 (templates/403.html).
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .perfis import Perfil


def perfil_required(*perfis):
    """Exige usuário autenticado, com um dos `perfis`, vinculado a uma filial.

    A filial é obrigatória porque todas as consultas são escopadas por filial
    (preparação para a Fase 2, múltiplas unidades). O superusuário criado por
    `createsuperuser` não tem filial e deve usar apenas o /admin/.
    """

    def decorador(view):
        @wraps(view)
        def interna(request, *args, **kwargs):
            usuario = request.user
            if usuario.perfil not in perfis or usuario.filial_id is None:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return login_required(interna)

    return decorador


somente_gerente = perfil_required(Perfil.GERENTE)
somente_funcionario = perfil_required(Perfil.FUNCIONARIO)
