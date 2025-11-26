from django import forms
from django.contrib.auth.models import User, Group
from .models import Ingreso, Egreso, InventarioItem

class CrearEmpleadoForm(forms.ModelForm):
    # Campos extra que no están directamente en el modelo User simple
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirmar Contraseña")
    
    # Selector de Rol (Filtramos para que no pueda crear otro Administrador si no quieres)
    rol = forms.ModelChoiceField(
        queryset=Group.objects.exclude(name='Administrador'), 
        label="Rol del Empleado",
        empty_label="Seleccione un rol"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm = cleaned_data.get("confirm_password")

        if password != confirm:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return cleaned_data


class IngresoForm(forms.ModelForm):
    class Meta:
        model = Ingreso
        fields = [
            'titulo',
            'descripcion',
            'monto',
            'operacional_noperacional',
            'cliente'
        ]
class EgresoForm(forms.ModelForm):
    class Meta:
        model = Egreso
        fields = [
            'titulo',
            'descripcion',
            'costo',
            'costo_gasto'
        ]

class InventarioForm(forms.ModelForm):
    class Meta:
        model = InventarioItem
        fields = [
            'nombre',
            'descripcion',
            'precio',
            'cantidad',
            'numero_factura'
        ]

class EditarUsuarioForm(forms.ModelForm):
    nueva_contrasena = forms.CharField(
        label="Nueva contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={'placeholder': 'Dejar vacío para no cambiar'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'nueva_contrasena']