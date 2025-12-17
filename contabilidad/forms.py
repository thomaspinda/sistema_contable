from django import forms
from django.contrib.auth.models import User, Group
from .models import Ingreso, Egreso, InventarioItem, Cliente, Liquidacion

class CrearEmpleadoForm(forms.ModelForm):
    # Campos extra que no están directamente en el modelo User simple
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirmar Contraseña")
    valor_hora = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Valor por Hora",
        initial=2700,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
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
            'cliente_link'
        ]
class EgresoForm(forms.ModelForm):
    class Meta:
        model = Egreso
        fields = [
            'titulo',
            'descripcion',
            'costo_gasto',
            'numero_factura'
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

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombre', 'email', 'telefono', 'direccion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
# forms.py
class ProductoCatalogoForm(forms.ModelForm):
    class Meta:
        model = InventarioItem
        fields = ['nombre', 'precio', 'descripcion'] # NO incluimos 'cantidad'
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class LiquidacionForm(forms.ModelForm):
    class Meta:
        model = Liquidacion
        fields = ['empleado', 'mes_correspondiente', 'horas_trabajadas', 'bonos', 'descuentos']
        widgets = {
            'empleado': forms.Select(attrs={'class': 'form-select'}),
            'mes_correspondiente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Marzo 2024'}),
            'horas_trabajadas': forms.NumberInput(attrs={'class': 'form-control'}),
            'bonos': forms.NumberInput(attrs={'class': 'form-control'}),
            'descuentos': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    # Filtramos para que solo aparezcan empleados activos, no admin general si no quieres
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Opcional: Filtrar queryset de empleados si es necesario

# forms.py

class CrearTrabajadorForm(forms.ModelForm):
    # Campo manual para el valor hora
    valor_hora = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        initial=2700, 
        label="Valor Hora ($)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        # NOTA: No incluimos 'password' ni 'rol'
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RUT'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'username': 'RUT',
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
        }