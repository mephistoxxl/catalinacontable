from django.http import Http404
from inventario.models import Empresa


def get_active_empresa(request):
    """Return active Empresa based on session + user linkage; raise Http404 if invalid."""
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id or not request.user.is_authenticated:
        raise Http404("Empresa no seleccionada")
    # Validate linkage
    if not request.user.empresas.filter(id=empresa_id).exists():
        raise Http404("Empresa no autorizada")
    try:
        return Empresa.objects.get(id=empresa_id)
    except Empresa.DoesNotExist:
        raise Http404("Empresa inexistente")


def ensure_tenant_object(model, **kwargs):
    """Fetch object restricted by empresa in kwargs; raises 404 if not matches."""
    return model.objects.filter(**kwargs).first()