from __future__ import annotations

from typing import Any


def plan_lock_context(request) -> dict[str, Any]:
    plan_lock = {
        'is_locked': False,
        'reason': '',
        'message': '',
        'estado_plan': None,
    }

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'plan_lock': plan_lock}

    empresa_id = request.session.get('empresa_activa')
    if not empresa_id:
        return {'plan_lock': plan_lock}

    try:
        empresa = user.empresas.filter(id=empresa_id).first()
        if not empresa:
            return {'plan_lock': plan_lock}

        from .utils_planes import obtener_estado_plan

        estado_plan = obtener_estado_plan(empresa)
        plan_lock['estado_plan'] = estado_plan

        if not estado_plan.get('tiene_plan'):
            return {'plan_lock': plan_lock}

        if estado_plan.get('periodo_vencido'):
            plan_lock['is_locked'] = True
            plan_lock['reason'] = 'periodo_vencido'
            plan_lock['message'] = (
                f"Tu periodo del plan {estado_plan.get('plan_nombre', '')} ha vencido. "
                "Contacta a soporte para renovar y continuar usando el panel."
            ).strip()
        elif estado_plan.get('alcanzado_limite'):
            plan_lock['is_locked'] = True
            plan_lock['reason'] = 'limite_alcanzado'
            plan_lock['message'] = (
                f"Alcanzaste el límite de {estado_plan.get('limite_documentos', 0)} documentos "
                f"del plan {estado_plan.get('plan_nombre', '')}. "
                "Actualiza tu plan para seguir operando."
            )
    except Exception:
        return {'plan_lock': plan_lock}

    return {'plan_lock': plan_lock}
