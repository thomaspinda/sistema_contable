from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
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
    cliente = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Cliente"
    )

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
    fecha = models.DateField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

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

    def __str__(self):
        return self.nombre
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # admin que creó este usuario
    creado_por = models.ForeignKey(
        User,
        related_name='usuarios_creados',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    requiere_cambio_password = models.BooleanField(default=True)
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
