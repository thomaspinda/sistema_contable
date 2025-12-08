from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import CrearEmpleadoForm, EditarUsuarioForm, IngresoForm, EgresoForm, InventarioForm
from .models import Ingreso, Egreso, InventarioItem, PasswordResetRequest
from itertools import chain
from operator import attrgetter
# Función de comprobación: ¿Es Administrador?
def es_administrador(user):
    return user.groups.filter(name='Administrador').exists() or user.is_superuser

@login_required
@user_passes_test(es_administrador) # Solo deja pasar si cumple la función de arriba
def crear_empleado(request):
    if request.method == 'POST':
        form = CrearEmpleadoForm(request.POST)
        if form.is_valid():
            # 1. Guardar usuario pero no escribir en BD todavía (commit=False)
            user = form.save(commit=False)
            user.save()

# ahora el profile ya existe gracias al signal
            user.profile.creado_por = request.user
            user.profile.save()

            user.set_password(form.cleaned_data['password'])
            user.save()

            # 3. Asignar el Grupo seleccionado
            mi_grupo = form.cleaned_data['rol']
            user.groups.add(mi_grupo)

            return redirect('dashboard') # O a la misma vista para crear otro
    else:
        form = CrearEmpleadoForm()

    return render(request, 'crear_empleado.html', {'form': form})

@login_required
def dashboard(request):
    # Lógica simple de redirección o renderizado según rol
    usuario = request.user
    
    rol = "Sin Asignar"
    profile = request.user.profile
    if profile.requiere_cambio_password:
        return redirect("cambiar_password_primera_vez")
    if usuario.groups.filter(name='Administrador').exists():
        rol = "Administrador"
        # Quizás quieras mostrar lista de empleados aquí
    elif usuario.groups.filter(name='Contador').exists():
        rol = "Contador"
    elif usuario.groups.filter(name='Almacenista').exists():
        rol = "Almacenista"

    return render(request, 'dashboard.html', {'rol': rol})

@login_required
def dashboard(request):
    usuario = request.user
    
    # Banderas de Rol
    es_admin = usuario.groups.filter(name='Administrador').exists() or usuario.is_superuser
    es_contador = usuario.groups.filter(name='Contador').exists()
    es_almacenista = usuario.groups.filter(name='Almacenista').exists()
    
    solicitudes = None
    historial_combinado = []

    if es_admin:
        solicitudes = PasswordResetRequest.objects.filter(atendido=False)

        # Traemos los últimos 10 de cada uno
        ingresos = Ingreso.objects.all().order_by('-fecha')[:10]
        egresos = Egreso.objects.all().order_by('-fecha')[:10]
        items = InventarioItem.objects.all().order_by('-fecha_ingreso')[:10]

        # --- ETIQUETADO Y NORMALIZACIÓN DE DATOS ---
        
        for i in ingresos:
            i.tipo_accion = 'Ingreso'
            i.css_class = 'success'
            i.fecha_orden = i.fecha
            # Normalizamos para la tabla:
            i.columna_detalle = i.descripcion  # O i.motivo, según tu modelo
            i.columna_valor = f"+ ${i.monto}"  # Formato dinero positivo

        for e in egresos:
            e.tipo_accion = 'Egreso'
            e.css_class = 'danger'
            e.fecha_orden = e.fecha
            # Normalizamos:
            e.columna_detalle = e.descripcion 
            e.columna_valor = f"- ${e.costo}"  # Formato dinero negativo

        for it in items:
            it.tipo_accion = 'Inventario'
            it.css_class = 'info'
            it.fecha_orden = it.fecha_ingreso
            # Normalizamos:
            it.columna_detalle = it.nombre     # El nombre del producto
            it.columna_valor = f"{it.cantidad} un." # Formato unidades

        # Combinar y Ordenar
        historial_combinado = sorted(
            chain(ingresos, egresos, items),
            key=attrgetter('fecha_orden'),
            reverse=True
        )

        # Opcional: Si solo quieres ver lo que hicieron "los demás", descomenta esto:
        # historial_combinado = [x for x in historial_combinado if x.creado_por != request.user]

    context = {
        'es_admin': es_admin,
        'es_contador': es_contador,
        'es_almacenista': es_almacenista,
        'nombre_usuario': usuario.first_name or usuario.username,
        'solicitudes': solicitudes,
        'historial': historial_combinado, # <--- Pasamos la lista nueva
    }
    
    return render(request, 'dashboard.html', context)

def es_contador_almacenista(user):
    return (user.groups.filter(name='Contador').exists() or
            user.groups.filter(name='Administrador').exists() or
            user.groups.filter(name='Almacenista').exists() or
            user.is_superuser)

# ----------------------------
# INGRESOS: page (form + lista)
# ----------------------------
@login_required
@user_passes_test(es_contador_almacenista)
def ingresos_page(request):
    # listamos todos los ingresos (más recientes primero)
    ingresos = Ingreso.objects.all().order_by('-fecha')

    if request.method == 'POST':
        form = IngresoForm(request.POST)
        if form.is_valid():
            ingreso = form.save(commit=False)
            ingreso.creado_por = request.user
            nombre_a_guardar = request.user.get_full_name() or request.user.username
            ingreso.creado_por_nombre_fijo = nombre_a_guardar
            ingreso.save()
            # redirigimos a la misma vista para evitar duplicar POST (PRG)
            return redirect('ingresos_page')
        else:
            # form inválido: se mostrará en la misma página con errores
            messages.error(request, 'Corrige los errores del formulario.')
    else:
        form = IngresoForm()

    return render(request, 'ingresos/ingresos.html', {
        'form': form,
        'ingresos': ingresos
    })

# ----------------------------
# EGRESOS: page (form + lista)
# ----------------------------
@login_required
@user_passes_test(es_contador_almacenista)
def egresos_page(request):
    egresos = Egreso.objects.all().order_by('-fecha')

    if request.method == 'POST':
        form = EgresoForm(request.POST)
        if form.is_valid():
            egreso = form.save(commit=False)
            egreso.creado_por = request.user
            nombre_a_guardar = request.user.get_full_name() or request.user.username
            egreso.creado_por_nombre_fijo = nombre_a_guardar
            egreso.save()
            return redirect('egresos_page')
        else:
            messages.error(request, 'Corrige los errores del formulario.')
    else:
        form = EgresoForm()

    return render(request, 'egresos/egresos.html', {
        'form': form,
        'egresos': egresos
    })

# ----------------------------
# INVENTARIO: page (form + lista)
# ----------------------------
@login_required
@user_passes_test(es_contador_almacenista)
def inventario_page(request):
    items = InventarioItem.objects.all().order_by('-fecha_ingreso')

    if request.method == 'POST':
        form = InventarioForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.creado_por = request.user
            nombre_a_guardar = request.user.get_full_name() or request.user.username
            item.creado_por_nombre_fijo = nombre_a_guardar
            item.save()
            return redirect('inventario_page')
        else:
            messages.error(request, 'Corrige los errores del formulario.')
    else:
        form = InventarioForm()

    return render(request, 'inventario/inventario.html', {
        'form': form,
        'items': items
    })


@login_required
def lista_usuarios(request):

    # Solo admins y superuser pueden ver esta lista
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    # Mostrar únicamente los usuarios creados por este admin
    usuarios_creados = User.objects.filter(profile__creado_por=request.user)


    return render(request, 'usuarios/lista_usuarios.html', {
        'usuarios': usuarios_creados
    })
@login_required
def editar_usuario(request, user_id):
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    usuario = get_object_or_404(User, id=user_id)
    form = EditarUsuarioForm(request.POST or None, instance=usuario)

    if request.method == "POST":
        if form.is_valid():
            user = form.save(commit=False)

            nueva_pass = form.cleaned_data.get('nueva_contrasena')
            if nueva_pass:
                user.set_password(nueva_pass)

            user.save()

            return redirect('lista_usuarios')

    return render(request, 'usuarios/editar_usuario.html', {
        'form': form,
        'usuario': usuario
    })

@login_required
def eliminar_usuario(request, user_id):

    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    usuario = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        usuario.delete()
        return redirect('lista_usuarios')

    return render(request, 'usuarios/eliminar_usuario.html', {
        'usuario': usuario
    })
@login_required
def cambiar_password_primera_vez(request):
    if request.method == "POST":
        nueva = request.POST.get("nueva_password")
        confirmar = request.POST.get("confirmar_password")

        if nueva != confirmar:
            messages.error(request, "Las contraseñas no coinciden.")
        elif len(nueva) < 6:
            messages.error(request, "La contraseña debe tener al menos 6 caracteres.")
        else:
            request.user.set_password(nueva)
            request.user.save()

            request.user.profile.requiere_cambio_password = False
            request.user.profile.save()

            return redirect("login")

    return render(request, "usuarios/cambiar_password_primera_vez.html")

def solicitar_reset_password(request):
    if request.method == "POST":
        username = request.POST.get("username")

        try:
            usuario = User.objects.get(username=username)

            PasswordResetRequest.objects.create(usuario=usuario)
            return redirect("login")

        except User.DoesNotExist:
            messages.error(request, "El usuario no existe.")

    return render(request, "usuarios/solicitar_reset_password.html")

@login_required
def marcar_solicitud_atendida(request, solicitud_id):
    # CORRECCIÓN: Agregamos el "not" y paréntesis
    # Si NO es admin y NO es superusuario, entonces lo echamos.
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect("dashboard")

    # Es buena práctica usar get_object_or_404 por si la ID no existe
    solicitud = get_object_or_404(PasswordResetRequest, id=solicitud_id)
    
    solicitud.atendido = True
    solicitud.save()

    return redirect("dashboard")
@login_required
def editar_movimiento(request, movimiento_tipo, movimiento_id):
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    if movimiento_tipo == 'ingreso':
        movimiento = get_object_or_404(Ingreso, id=movimiento_id)
        FormClass = IngresoForm
        template_name = 'ingresos/editar_ingreso.html'
    elif movimiento_tipo == 'egreso':
        movimiento = get_object_or_404(Egreso, id=movimiento_id)
        FormClass = EgresoForm
        template_name = 'egresos/editar_egreso.html'
    elif movimiento_tipo == 'inventario':
        movimiento = get_object_or_404(InventarioItem, id=movimiento_id)
        FormClass = InventarioForm
        template_name = 'inventario/editar_item.html'
    else:
        messages.error(request, "Tipo de movimiento inválido.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = FormClass(request.POST, instance=movimiento)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = FormClass(instance=movimiento)

    return render(request, template_name, {
        'form': form,
        'movimiento': movimiento
    })
@login_required
def eliminar_movimiento(request, movimiento_tipo, movimiento_id):
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    if movimiento_tipo == 'ingreso':
        movimiento = get_object_or_404(Ingreso, id=movimiento_id)
        template_name = 'ingresos/eliminar_ingreso.html'
    elif movimiento_tipo == 'egreso':
        movimiento = get_object_or_404(Egreso, id=movimiento_id)
        template_name = 'egresos/eliminar_egreso.html'
    elif movimiento_tipo == 'inventario':
        movimiento = get_object_or_404(InventarioItem, id=movimiento_id)
        template_name = 'inventario/eliminar_item.html'
    else:
        messages.error(request, "Tipo de movimiento inválido.")
        return redirect('dashboard')

    if request.method == 'POST':
        movimiento.delete()
        return redirect('dashboard')

    return render(request, template_name, {
        'movimiento': movimiento
    })
@login_required
def editar_item_inventario(request, item_id):
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    item = get_object_or_404(InventarioItem, id=item_id)

    if request.method == 'POST':
        form = InventarioForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, "Artículo de inventario actualizado correctamente.")
            return redirect('dashboard')
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = InventarioForm(instance=item)

    return render(request, 'inventario/editar_item.html', {
        'form': form,
        'item': item
    })
@login_required
def eliminar_item_inventario(request, item_id):
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    item = get_object_or_404(InventarioItem, id=item_id)

    if request.method == 'POST':
        item.delete()
        return redirect('dashboard')

    return render(request, 'inventario/eliminar_item.html', {
        'item': item
    })
