from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import CrearEmpleadoForm, EditarUsuarioForm, IngresoForm, EgresoForm, InventarioForm
from .models import Ingreso, Egreso, InventarioItem

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

            messages.success(request, f"Empleado {user.username} creado con el rol {mi_grupo.name}")
            return redirect('dashboard') # O a la misma vista para crear otro
    else:
        form = CrearEmpleadoForm()

    return render(request, 'crear_empleado.html', {'form': form})

@login_required
def dashboard(request):
    # Lógica simple de redirección o renderizado según rol
    usuario = request.user
    rol = "Sin Asignar"
    
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
    
    # Verificamos pertenencia a grupos para pasar banderas al template
    es_admin = usuario.groups.filter(name='Administrador').exists() or usuario.is_superuser
    es_contador = usuario.groups.filter(name='Contador').exists()
    es_almacenista = usuario.groups.filter(name='Almacenista').exists()

    context = {
        'es_admin': es_admin,
        'es_contador': es_contador,
        'es_almacenista': es_almacenista,
        'nombre_usuario': usuario.first_name or usuario.username
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
            ingreso.save()
            messages.success(request, 'Ingreso registrado correctamente.')
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
            egreso.save()
            messages.success(request, 'Egreso registrado correctamente.')
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
            item.save()
            messages.success(request, 'Artículo registrado correctamente.')
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

            messages.success(request, "Usuario actualizado correctamente.")
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
        messages.success(request, "Usuario eliminado correctamente.")
        return redirect('lista_usuarios')

    return render(request, 'usuarios/eliminar_usuario.html', {
        'usuario': usuario
    })
