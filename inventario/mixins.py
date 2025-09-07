from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden


def require_empresa_activa(view_func):
    """Decorator that ensures an active empresa is set in session and the user belongs to it."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            return redirect('inventario:seleccionar_empresa')
        if not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden('No pertenece a esta empresa')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


class RequireEmpresaActivaMixin:
    """Mixin for class-based views to enforce presence of an active empresa."""
    def dispatch(self, request, *args, **kwargs):
        empresa_id = request.session.get('empresa_activa')
        if not empresa_id:
            return redirect('inventario:seleccionar_empresa')
        if not request.user.empresas.filter(id=empresa_id).exists():
            return HttpResponseForbidden('No pertenece a esta empresa')
        return super().dispatch(request, *args, **kwargs)
