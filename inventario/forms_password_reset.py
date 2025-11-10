from django import forms
from django.core.exceptions import ValidationError
from .models import Usuario, Empresa


class SolicitarResetPasswordForm(forms.Form):
    """
    Formulario para solicitar reseteo de contraseña.
    Requiere cédula/RUC Y email, ambos deben coincidir.
    """
    identificacion = forms.CharField(
        max_length=13,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Ingrese su cédula o RUC',
            'autocomplete': 'off'
        }),
        label='Cédula o RUC'
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'correo@ejemplo.com',
            'autocomplete': 'email'
        }),
        label='Correo Electrónico'
    )

    def clean_identificacion(self):
        identificacion = self.cleaned_data.get('identificacion', '').strip()
        
        # Validar que sea numérico
        if not identificacion.isdigit():
            raise ValidationError('La identificación debe contener solo números.')
        
        # Validar longitud (10 para cédula, 13 para RUC)
        if len(identificacion) not in [10, 13]:
            raise ValidationError('Ingrese una cédula válida (10 dígitos) o RUC (13 dígitos).')
        
        return identificacion

    def clean(self):
        """
        Valida que la identificación y el email estén relacionados.
        """
        cleaned_data = super().clean()
        identificacion = cleaned_data.get('identificacion')
        email = cleaned_data.get('email')
        
        if not identificacion or not email:
            return cleaned_data
        
        # Buscar en usuarios (cédula)
        if len(identificacion) == 10:
            try:
                usuario = Usuario.objects.get(username=identificacion)
                if not usuario.email:
                    raise ValidationError('El usuario no tiene un correo electrónico registrado.')
                
                # Verificar que el email coincida
                if usuario.email.lower() != email.lower():
                    raise ValidationError('La cédula y el correo electrónico no coinciden.')
                
                # Guardar el usuario para usarlo después
                self.usuario_encontrado = usuario
                
            except Usuario.DoesNotExist:
                raise ValidationError('No se encontró un usuario con esa cédula.')
        
        # Buscar en empresas (RUC)
        elif len(identificacion) == 13:
            try:
                empresa = Empresa.objects.get(ruc=identificacion)
                usuarios_empresa = empresa.usuarios.all()
                
                # Buscar usuario con el email proporcionado
                usuario_encontrado = None
                for usuario in usuarios_empresa:
                    if usuario.email and usuario.email.lower() == email.lower():
                        usuario_encontrado = usuario
                        break
                
                if not usuario_encontrado:
                    raise ValidationError('El RUC y el correo electrónico no coinciden o no están registrados juntos.')
                
                # Guardar el usuario para usarlo después
                self.usuario_encontrado = usuario_encontrado
                
            except Empresa.DoesNotExist:
                raise ValidationError('No se encontró una empresa con ese RUC.')
        
        return cleaned_data

    def get_usuario(self):
        """
        Retorna el usuario validado.
        """
        return getattr(self, 'usuario_encontrado', None)


class ResetPasswordForm(forms.Form):
    """
    Formulario para establecer nueva contraseña.
    """
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Nueva contraseña'
        }),
        label='Nueva contraseña',
        min_length=8
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Confirmar contraseña'
        }),
        label='Confirmar contraseña'
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2 and password1 != password2:
            raise ValidationError('Las contraseñas no coinciden.')

        return cleaned_data
