from django.utils import timezone

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import random
import string
from datetime import timedelta

class AuditoriaMovimiento(models.Model):
    TIPO_ACCION = [
        ('EDICION', 'Edición'),
        ('ELIMINACION', 'Eliminación'),
    ]
    
    tipo_movimiento = models.CharField(max_length=20) # Ingreso, Egreso, Inventario
    id_original = models.IntegerField()
    accion = models.CharField(max_length=20, choices=TIPO_ACCION)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha_cambio = models.DateTimeField(auto_now_add=True)
    detalles_anteriores = models.TextField() # Guardaremos el estado previo del registro

    def __str__(self):
        return f"{self.accion} - {self.tipo_movimiento} por {self.usuario}"

class Cliente(models.Model):
    nombre = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.nombre
# ---------------------------------------
# MODELO: INGRESOS
# ---------------------------------------
class Ingreso(models.Model):
    titulo = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    monto = models.PositiveIntegerField()
    fecha = models.DateField(auto_now_add=True)
    operacional_noperacional = models.CharField(
        max_length=20,
        default='Operacional',
        choices=[
            ('Operacional', 'Operacional'),
            ('No Operacional', 'No Operacional')
        ],
        verbose_name="Tipo de Ingreso"
    )
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    creado_por_nombre_fijo = models.CharField(max_length=150, null=True, blank=True)

    cliente_link = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Seleccionar Cliente")
    activo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.titulo} - ${self.monto}"


# ---------------------------------------
# MODELO: EGRESOS
# ---------------------------------------
class Egreso(models.Model):
    titulo = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    costo = models.PositiveIntegerField()
    costo_gasto = models.CharField(
        max_length=20,
        default='Costo',
        choices=[
            ('Costo', 'Costo'),
            ('Gasto', 'Gasto')
        ],
        verbose_name="Tipo de Egreso"
    )
    numero_factura = models.PositiveIntegerField(default=0)
    fecha = models.DateField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    creado_por_nombre_fijo = models.CharField(max_length=150, null=True, blank=True)
    activo = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.titulo} - ${self.costo}"


# ---------------------------------------
# MODELO: INVENTARIO
# ---------------------------------------
class InventarioItem(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.PositiveIntegerField()
    cantidad = models.PositiveIntegerField(
        default=0,
        verbose_name="Cantidad en Stock"
    )
    fecha_ingreso = models.DateField(auto_now_add=True)
    numero_factura = models.CharField(max_length=50)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    creado_por_nombre_fijo = models.CharField(max_length=150, null=True, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    creado_por = models.ForeignKey(
        User,
        related_name='usuarios_creados',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    requiere_cambio_password = models.BooleanField(default=True)
    
    # --- CAMPO NUEVO AGREGADO AQUÍ ---
    valor_hora = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=2700.00, 
        verbose_name="Valor por Hora"
    )

    def __str__(self):
        return f"Perfil de {self.user.username}"
@receiver(post_save, sender=User)
def crear_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def guardar_profile(sender, instance, **kwargs):
    instance.profile.save()

class PasswordResetRequest(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    atendido = models.BooleanField(default=False)

    def __str__(self):
        return f"Solicitud de {self.usuario.username} ({'Atendida' if self.atendido else 'Pendiente'})"

class DetalleIngreso(models.Model):
    # Vincula con el Ingreso "padre" (la cabecera de la factura)
    ingreso = models.ForeignKey(Ingreso, on_delete=models.CASCADE, related_name='detalles')
    # Vincula con el Producto del inventario
    producto = models.ForeignKey(InventarioItem, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"
class DetalleEgreso(models.Model):
    # Vincula con el Egreso "padre"
    egreso = models.ForeignKey(Egreso, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(InventarioItem, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"



# 2. NUEVO MODELO: Liquidacion
class Liquidacion(models.Model):
    empleado = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_pago = models.DateField(auto_now_add=True)
    mes_correspondiente = models.CharField(max_length=20, verbose_name="Mes/Año (Ej: Enero 2024)")
    horas_trabajadas = models.DecimalField(max_digits=5, decimal_places=1)
    valor_hora_aplicado = models.DecimalField(max_digits=10, decimal_places=2)
    bonos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuentos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Este es el total final (Sueldo Neto)
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2)
    
    registrado_por = models.ForeignKey(User, related_name='nominas_creadas', on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Sueldo {self.empleado.username} - {self.mes_correspondiente}"
class CodigoVerificacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    codigo = models.CharField(max_length=6)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    utilizado = models.BooleanField(default=False)

    def es_valido(self):
        return not self.utilizado and timezone.now() < self.fecha_creacion + timedelta(minutes=10)

    def generar_codigo(self):
        self.codigo = ''.join(random.choices(string.digits, k=6))
        self.save()


class Cotizacion(models.Model):
    cliente_nombre = models.CharField()
    fecha = models.DateTimeField(auto_now_add=True)
    horas_estimadas = models.DecimalField(max_digits=6, decimal_places=1)
    valor_hora_aplicado = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion_servicio = models.TextField()
    total_materiales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cotizacion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Cotizacion {self.id} - {self.cliente_nombre}"

class ItemCotizacion(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, related_name='items', on_delete=models.CASCADE)
    producto = models.ForeignKey(InventarioItem, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario_momento = models.DecimalField(max_digits=10, decimal_places=2)