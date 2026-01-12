"""Vistas para Notas de Débito.

Nota: este módulo se deja scaffolded (estructura base) para implementar el flujo
completo en siguientes commits.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from inventario.views import complementarContexto

logger = logging.getLogger(__name__)


class ListarNotasDebito(LoginRequiredMixin, View):
    login_url = '/inventario/login'

    def get(self, request):
        contexto = {
            'titulo': 'Notas de Débito',
        }
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/nota_debito/listar.html', contexto)


class CrearNotaDebito(LoginRequiredMixin, View):
    login_url = '/inventario/login'

    def get(self, request, factura_id=None):
        messages.info(request, 'Módulo Nota de Débito: en construcción.')
        return render(request, 'inventario/nota_debito/crear.html', complementarContexto({}, request.user))

    def post(self, request, factura_id=None):
        return HttpResponse('Not implemented', status=501)


class VerNotaDebito(LoginRequiredMixin, View):
    login_url = '/inventario/login'

    def get(self, request, nota_debito_id):
        messages.info(request, 'Módulo Nota de Débito: en construcción.')
        contexto = {'titulo': 'Nota de Débito'}
        contexto = complementarContexto(contexto, request.user)
        return render(request, 'inventario/nota_debito/ver.html', contexto)
