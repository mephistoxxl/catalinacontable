"""Helper para centralizar el ambiente SRI ('1' pruebas, '2' producción)."""
from django.conf import settings


def obtener_ambiente_sri(empresa=None) -> str:
    """Retorna '1' (pruebas) o '2' (producción) desde empresa.tipo_ambiente.

    Fallback a settings.SRI_AMBIENTE o '1'.
    """
    try:
        amb = getattr(empresa, 'tipo_ambiente', None)
        if amb in ('1', '2'):
            return amb
    except Exception:
        pass
    return getattr(settings, 'SRI_AMBIENTE', '1')
