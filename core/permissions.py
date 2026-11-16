from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Funcionario as F


def perfil_required(*perfis):
    """Restringe a view aos perfis informados (Administrador sempre pode)."""
    permitidos = set(perfis) | {F.ADMINISTRADOR}

    def deco(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.perfil not in permitidos:
                messages.error(request, "Seu perfil não tem acesso a essa função.")
                return redirect("painel")
            return view(request, *args, **kwargs)
        return wrapper
    return deco
