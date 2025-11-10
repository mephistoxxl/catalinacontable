"""
Vistas para reseteo de contraseña
"""
import secrets
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
import logging

from .models import Usuario, Empresa, PasswordResetToken
from .forms_password_reset import SolicitarResetPasswordForm, ResetPasswordForm

logger = logging.getLogger(__name__)


class SolicitarResetPassword(View):
    """
    Vista AJAX para solicitar reseteo de contraseña.
    Recibe cédula o RUC, busca el email y envía link de reseteo.
    """
    
    def post(self, request):
        form = SolicitarResetPasswordForm(request.POST)
        
        if form.is_valid():
            try:
                # Obtener usuario validado (ya verificado que email coincida)
                usuario = form.get_usuario()
                email = usuario.email
                identificacion = form.cleaned_data['identificacion']
                
                # Generar token único y seguro
                token = secrets.token_urlsafe(32)
                
                # Guardar token en base de datos
                reset_token = PasswordResetToken.objects.create(
                    usuario=usuario,
                    token=token
                )
                
                # Construir URL de reseteo
                reset_url = request.build_absolute_uri(
                    reverse('inventario:reset_password', kwargs={'token': token})
                )
                
                # Preparar email
                tipo_desc = 'cédula' if len(identificacion) == 10 else 'RUC de empresa'
                
                asunto = 'Recuperación de Contraseña - Sistema de Facturación'
                mensaje = f"""
Hola {usuario.get_full_name() or usuario.username},

Recibimos una solicitud para restablecer la contraseña asociada a:
- {tipo_desc}: {identificacion}
- Email: {email}

Para crear una nueva contraseña, haz clic en el siguiente enlace (válido por 1 hora):

{reset_url}

Si no solicitaste este cambio, puedes ignorar este correo de forma segura.

---
Sistema de Facturación Electrónica
Catalina Facturador
                """
                
                # Enviar email
                send_mail(
                    subject=asunto,
                    message=mensaje,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                logger.info(f"✅ Email de reseteo enviado a {email} para usuario {usuario.username}")
                
                return render(request, 'inventario/password_reset/solicitar_ajax.html', {
                    'success': True,
                    'email': email,
                    'message': f'Se ha enviado un correo a {email} con las instrucciones para restablecer tu contraseña.'
                })
                
            except Exception as e:
                logger.error(f"❌ Error enviando email de reseteo: {e}")
                return render(request, 'inventario/password_reset/solicitar_ajax.html', {
                    'success': False,
                    'error': 'Ocurrió un error al enviar el correo. Por favor, intenta nuevamente.'
                })
        
        # Si el formulario no es válido
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)
        
        return render(request, 'inventario/password_reset/solicitar_ajax.html', {
            'success': False,
            'errors': errors
        })


class ResetPassword(View):
    """
    Vista para validar token y cambiar contraseña.
    """
    
    def get(self, request, token):
        # Validar token
        try:
            reset_token = PasswordResetToken.objects.get(token=token)
            
            if not reset_token.is_valid():
                messages.error(request, 'Este enlace de recuperación ha expirado o ya fue utilizado. Por favor, solicita uno nuevo.')
                return redirect('inventario:login')
            
            form = ResetPasswordForm()
            return render(request, 'inventario/password_reset/reset_password.html', {
                'form': form,
                'token': token,
                'usuario': reset_token.usuario
            })
            
        except PasswordResetToken.DoesNotExist:
            messages.error(request, 'Enlace de recuperación inválido.')
            return redirect('inventario:login')
    
    def post(self, request, token):
        # Validar token
        try:
            reset_token = PasswordResetToken.objects.get(token=token)
            
            if not reset_token.is_valid():
                messages.error(request, 'Este enlace de recuperación ha expirado o ya fue utilizado.')
                return redirect('inventario:login')
            
            form = ResetPasswordForm(request.POST)
            
            if form.is_valid():
                # Cambiar contraseña
                nueva_password = form.cleaned_data['password1']
                usuario = reset_token.usuario
                usuario.set_password(nueva_password)
                usuario.save()
                
                # Marcar token como usado
                reset_token.mark_as_used()
                
                logger.info(f"✅ Contraseña cambiada exitosamente para usuario {usuario.username}")
                
                messages.success(request, '✅ Tu contraseña ha sido cambiada exitosamente. Ya puedes iniciar sesión.')
                return redirect('inventario:login')
            
            # Si el formulario no es válido
            return render(request, 'inventario/password_reset/reset_password.html', {
                'form': form,
                'token': token,
                'usuario': reset_token.usuario
            })
            
        except PasswordResetToken.DoesNotExist:
            messages.error(request, 'Enlace de recuperación inválido.')
            return redirect('inventario:login')
