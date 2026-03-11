from django import template
register = template.Library()

@register.filter(name='add_class')
def add_class(field, css):
    return field.as_widget(attrs={**getattr(field.field.widget, 'attrs', {}), 'class': css})


@register.filter(name='display_sri_estado')
def display_sri_estado(value):
    estado = (value or '').strip().upper()
    if estado in {'AUTORIZADA', 'AUTORIZADO'}:
        return 'AUTORIZADO'
    if estado in {'RECHAZADA', 'RECHAZADO', 'NO_AUTORIZADA', 'NO AUTORIZADA', 'NO_AUTORIZADO', 'NO AUTORIZADO'}:
        return 'NO AUTORIZADO'
    if estado in {'PENDIENTE', 'RECIBIDA', 'ENVIADO', 'BORRADOR', ''}:
        return 'AUTORIZANDO'
    return value or ''
