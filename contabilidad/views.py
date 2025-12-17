from django.utils import timezone
from urllib import request
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import CrearEmpleadoForm, CrearTrabajadorForm, EditarUsuarioForm, IngresoForm, EgresoForm, InventarioForm, ClienteForm, LiquidacionForm, ProductoCatalogoForm
from .models import AuditoriaMovimiento, Cliente, CodigoVerificacion, Cotizacion, Ingreso, Egreso, InventarioItem, ItemCotizacion, PasswordResetRequest, DetalleIngreso, DetalleEgreso, Liquidacion
from itertools import chain
from operator import attrgetter
import json
from django.db import transaction
from django.db.models import Sum, Q
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.core.mail import send_mail
from django.contrib.auth.hashers import make_password
# Función de comprobación: ¿Es Administrador?
def es_administrador(user):
    return user.groups.filter(name='Administrador').exists() or user.is_superuser

@login_required
@user_passes_test(es_administrador)
def crear_empleado(request):
    if request.method == 'POST':
        form = CrearEmpleadoForm(request.POST)
        if form.is_valid():
            # 1. Guardar usuario básico
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # 2. Configurar el Perfil (Profile)
            # El profile ya se creó automáticamente por el Signal (post_save),
            # así que solo lo consultamos y actualizamos.
            user.profile.creado_por = request.user
            
            # --- AQUÍ GUARDAMOS EL VALOR HORA ---
            user.profile.valor_hora = form.cleaned_data['valor_hora']
            
            user.profile.save()

            # 3. Asignar Grupo
            mi_grupo = form.cleaned_data['rol']
            user.groups.add(mi_grupo)

            messages.success(request, f"Empleado {user.username} creado con valor hora ${user.profile.valor_hora}")
            return redirect('dashboard')
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

# views.py

@login_required
def dashboard(request):
    usuario = request.user
    profile = request.user.profile

    # 1. Verificar si requiere cambio de contraseña


    # 2. Determinar Roles
    es_admin = usuario.groups.filter(name='Administrador').exists() or usuario.is_superuser
    es_contador = usuario.groups.filter(name='Contador').exists()
    es_almacenista = usuario.groups.filter(name='Almacenista').exists()
    
    solicitudes = None
    ultimas_operaciones = []
    inventario_completo = []
    logs_auditoria = []

    # --- BLOQUE SOLO PARA ADMIN (Solicitudes y Auditoría) ---
    if es_admin:
        solicitudes = PasswordResetRequest.objects.filter(atendido=False)
        logs_auditoria = AuditoriaMovimiento.objects.all().order_by('-fecha_cambio')

    # --- BLOQUE DE DATOS GENERALES (Visible para Admin, Contador y Almacenista) ---
    # Si el usuario tiene CUALQUIER rol, cargamos los datos
    if es_admin or es_contador or es_almacenista:
        
        # A) Operaciones (Ingresos y Egresos)
        # Nota: Usamos filter(activo=True) por la eliminación lógica
        ingresos = Ingreso.objects.filter(activo=True).order_by('-fecha')
        egresos = Egreso.objects.filter(activo=True).order_by('-fecha')

        # Normalizamos datos para la tabla
        for i in ingresos:
            i.tipo = 'Ingreso'
            i.monto_visual = i.monto
            i.fecha_orden = i.fecha

        for e in egresos:
            e.tipo = 'Egreso'
            e.monto_visual = e.costo
            e.fecha_orden = e.fecha

        # Unimos y ordenamos
        ultimas_operaciones = sorted(
            chain(ingresos, egresos),
            key=attrgetter('fecha_orden'),
            reverse=True
        )

        # B) Inventario
        inventario_completo = InventarioItem.objects.all().filter(activo=True).order_by('-fecha_ingreso')

    context = {
        'es_admin': es_admin,
        'es_contador': es_contador,
        'es_almacenista': es_almacenista,
        'nombre_usuario': usuario.first_name or usuario.username,
        'solicitudes': solicitudes,
        'ultimas_operaciones': ultimas_operaciones, 
        'inventario': inventario_completo,
        'auditorias': logs_auditoria
    }
    
    return render(request, 'dashboard.html', context)

def es_contador_almacenista(user):
    return (user.groups.filter(name='Contador').exists() or
            user.groups.filter(name='Administrador').exists() or
            user.groups.filter(name='Almacenista').exists() or
            user.is_superuser)


@login_required
@user_passes_test(es_contador_almacenista)
def registrar_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            cliente.creado_por = request.user
            cliente.save()
            messages.success(request, f"Cliente {cliente.nombre} registrado.")
            return redirect('dashboard')
    else:
        form = ClienteForm()
    return render(request, 'usuarios/registrar_cliente.html', {'form': form})
@login_required
@user_passes_test(es_contador_almacenista)
def lista_clientes(request):
    clientes = Cliente.objects.all().order_by('nombre')
    return render(request, 'usuarios/lista_clientes.html', {'clientes': clientes})

# ----------------------------
# INGRESOS: page (form + lista)
# ----------------------------
@login_required
@user_passes_test(es_contador_almacenista)
def ingresos_page(request):
    ingresos = Ingreso.objects.all().order_by('-fecha')
    clientes = Cliente.objects.all()
    # Traemos TODOS los productos para el selector
    productos_disponibles = InventarioItem.objects.all() 

    if request.method == 'POST':
        form = IngresoForm(request.POST)
        
        # Usamos transaction.atomic para que si algo falla, no se guarde nada a medias
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Guardar el Ingreso principal (Cabecera)
                    ingreso = form.save(commit=False)
                    ingreso.creado_por = request.user
                    ingreso.save()
                    
                    # 2. Procesar los productos seleccionados (vienen del HTML)
                    productos_ids = request.POST.getlist('producto_id[]')
                    cantidades = request.POST.getlist('cantidad[]')
                    
                    for prod_id, cant in zip(productos_ids, cantidades):
                        if prod_id and cant: # Verificar que no estén vacíos
                            cantidad_int = int(cant)
                            producto = InventarioItem.objects.get(id=prod_id)
                            
                            # Verificación de Stock (Opcional pero recomendado)
                            if producto.cantidad < cantidad_int:
                                raise ValueError(f"No hay suficiente stock de {producto.nombre}")

                            # 3. Crear el registro en el modelo nuevo (Detalle)
                            DetalleIngreso.objects.create(
                                ingreso=ingreso,
                                producto=producto,
                                cantidad=cantidad_int
                            )
                            
                            # 4. Descontar del Inventario Original
                            producto.cantidad -= cantidad_int
                            producto.save()

                    messages.success(request, 'Ingreso y stock actualizados correctamente.')
                    return redirect('ingresos_page')

            except ValueError as e:
                # Si falta stock, mostramos el error y no guardamos nada
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Ocurrió un error: {e}")
                
    else:
        form = IngresoForm()

    return render(request, 'ingresos/ingresos.html', {
        'form': form,
        'ingresos': ingresos,
        'clientes': clientes,
        'productos': productos_disponibles # Pasamos los productos al template
    })
# ----------------------------
# EGRESOS: page (form + lista)
# ----------------------------
# views.py
from .models import Egreso, InventarioItem, DetalleEgreso # Asegúrate de tener este import

# views.py
from .models import Egreso, InventarioItem, DetalleEgreso
from django.db import transaction

# views.py

@login_required
@user_passes_test(es_contador_almacenista)
def egresos_page(request):
    egresos = Egreso.objects.filter(activo=True).order_by('-fecha')
    
    # Obtenemos objetos completos, no solo nombres, para saber sus precios
    productos_qs = InventarioItem.objects.all()
    precios_dict = {p.nombre: float(p.precio) for p in productos_qs}
    if request.method == 'POST':
        form = EgresoForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Preparamos el Egreso pero NO lo guardamos aún
                    # porque necesitamos calcular el costo total real.
                    egreso = form.save(commit=False)
                    egreso.creado_por = request.user
                    
                    # Inicializamos el acumulador de costo
                    costo_total_calculado = 0 
                    
                    # Guardamos temporalmente para tener ID (necesario para ManyToMany si usaras, 
                    # pero aquí usaremos DetalleEgreso que requiere el ID del egreso)
                    egreso.costo = 0 # Valor temporal
                    egreso.save()
                    
                    # 2. Capturamos los arrays del formulario
                    nombres = request.POST.getlist('nombre_producto[]')
                    cantidades = request.POST.getlist('cantidad[]')
                    precios = request.POST.getlist('precio_unitario[]')
                    
                    hay_items = False

                    for nombre, cant, precio_str in zip(nombres, cantidades, precios):
                        nombre_limpio = nombre.strip().title()
                        
                        if nombre_limpio and cant and precio_str:
                            hay_items = True
                            cantidad_int = int(cant)
                            precio_unitario = float(precio_str)
                            
                            # Cálculo del costo de esta línea
                            subtotal_linea = cantidad_int * precio_unitario
                            costo_total_calculado += subtotal_linea

                            # --- LÓGICA DE INVENTARIO (BUSCAR O CREAR) ---
                            producto, creado = InventarioItem.objects.get_or_create(
                                nombre=nombre_limpio,
                                defaults={
                                    'cantidad': 0,
                                    'precio': precio_unitario, # Si es nuevo, este es su precio base
                                    'descripcion': 'Ingreso automático por compra'
                                }
                            )

                            # Actualizar precio referencia (último costo de compra)
                            producto.precio = precio_unitario
                            
                            # Aumentar Stock
                            producto.cantidad += cantidad_int
                            producto.save()

                            # Crear Detalle
                            DetalleEgreso.objects.create(
                                egreso=egreso,
                                producto=producto,
                                cantidad=cantidad_int
                            )
                    
                    if not hay_items:
                        raise ValueError("Debe agregar al menos un item con cantidad y precio.")

                    # 3. ACTUALIZACIÓN FINAL DEL EGRESO
                    # Guardamos el costo real calculado matemáticamente
                    egreso.costo = costo_total_calculado
                    egreso.save()

                    messages.success(request, f'Egreso registrado. Costo Total calculado: ${costo_total_calculado}')
                    return redirect('egresos_page')

            except Exception as e:
                messages.error(request, f"Error al procesar: {e}")
    else:
        form = EgresoForm()

    return render(request, 'egresos/egresos.html', {
        'form': form,
        'egresos': egresos,
        # Pasamos los productos para que el JS sepa los precios actuales
        'precios_json': json.dumps(precios_dict)    
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

    return render(request, 'inventarios/inventario.html', {
        'form': form,
        'items': items
    })


@login_required
@user_passes_test(es_administrador)
def lista_usuarios(request):
    
    # 1. Primero definimos la base: Solo usuarios creados por este admin
    # (Esto asegura que cada admin vea solo a su gente)
    usuarios = User.objects.filter(profile__creado_por=request.user)

    # 2. Capturamos la búsqueda
    query = request.GET.get('q')

    # 3. Si hay búsqueda, filtramos SOBRE la lista que ya teníamos
    if query:
        usuarios = usuarios.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) 
        )

    # 4. Finalmente ordenamos
    usuarios = usuarios.order_by('username')

    # Validación de seguridad extra (opcional si ya usas el decorador)
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    # 5. Enviamos la variable 'usuarios' que ya tiene ambos filtros aplicados
    return render(request, 'usuarios/lista_usuarios.html', {
        'usuarios': usuarios,  # Aquí estaba el error antes, usabas otra variable
        'query': query
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
        datos_previos = f"Titulo: {movimiento.titulo}, Descripción: {movimiento.descripcion}, Monto: {movimiento.monto}, Operacional/No Operacional: {movimiento.operacional_noperacional}, Cliente: {movimiento.cliente_link}"
        FormClass = IngresoForm
        template_name = 'ingresos/editar_ingreso.html'
    elif movimiento_tipo == 'egreso':
        movimiento = get_object_or_404(Egreso, id=movimiento_id)
        datos_previos = f"Titulo: {movimiento.titulo}, Descripción: {movimiento.descripcion}, Costo: {movimiento.costo}, Costo/Gasto: {movimiento.costo_gasto}"
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
            AuditoriaMovimiento.objects.create(
                tipo_movimiento=movimiento_tipo.capitalize(),
                id_original=movimiento_id,
                accion='EDICION',
                usuario=request.user,
                detalles_anteriores=datos_previos
            )
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
        template_name = 'inventarios/eliminar_item.html'
    else:
        messages.error(request, "Tipo de movimiento inválido.")
        return redirect('dashboard')

    model_map = { 'ingreso': Ingreso, 'egreso': Egreso, 'inventario': InventarioItem }
    movimiento = get_object_or_404(model_map[movimiento_tipo], id=movimiento_id)
    if request.method == 'POST':
        AuditoriaMovimiento.objects.create(
            tipo_movimiento=movimiento_tipo.capitalize(),
            id_original=movimiento_id,
            accion='ELIMINACION',
            usuario=request.user,
            detalles_anteriores=f"Eliminado registro: {movimiento}"
        )
        movimiento.activo = False
        movimiento.save()
        return redirect('dashboard')

    return render(request, f'{movimiento_tipo}s/eliminar_{movimiento_tipo}.html', {'movimiento': movimiento})
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

    return render(request, 'inventarios/eliminar_item.html', {
        'item': item
    })
# views.py
@login_required
@user_passes_test(es_contador_almacenista)
def crear_item_catalogo(request):
    if request.method == 'POST':
        form = ProductoCatalogoForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.cantidad = 0  # REGLA DE NEGOCIO: Almacenista inicia en 0
            item.save()
            messages.success(request, f"Producto '{item.nombre}' añadido al catálogo con Stock 0.")
            return redirect('dashboard')
    else:
        form = ProductoCatalogoForm()
    
    return render(request, 'inventarios/crear_item.html', {'form': form})

@login_required
@user_passes_test(es_administrador) # Solo admin o RH debería ver esto
def registrar_sueldo(request):
    if request.method == 'POST':
        form = LiquidacionForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    liquidacion = form.save(commit=False)
                    
                    # 1. Obtener datos del empleado seleccionado
                    empleado = liquidacion.empleado
                    # Usamos el valor hora guardado en su perfil
                    # (Asegúrate de que UserProfile tenga valor_hora, si no dará error)
                    if hasattr(empleado, 'profile'):
                        valor_hora = empleado.profile.valor_hora
                    else:
                        valor_hora = 0
                        
                    if valor_hora <= 0:
                        raise ValueError(f"El empleado {empleado.username} no tiene configurado un Valor Hora en su perfil.")

                    # 2. Cálculos Matemáticos
                    subtotal = liquidacion.horas_trabajadas * valor_hora
                    total_final = subtotal + liquidacion.bonos - liquidacion.descuentos
                    
                    # Guardamos los datos calculados en el modelo Liquidacion
                    liquidacion.valor_hora_aplicado = valor_hora
                    liquidacion.total_pagar = total_final
                    liquidacion.registrado_por = request.user
                    liquidacion.save()

                    # 3. AUTOMATIZACIÓN: Crear el Egreso Financiero
                    # Esto conecta con tu Balance General automáticamente
                    Egreso.objects.create(
                        titulo=f"Nómina: {empleado.first_name} {empleado.last_name}",
                        descripcion=f"Pago de sueldo mes {liquidacion.mes_correspondiente}. {liquidacion.horas_trabajadas} hrs trabajadas.",
                        costo_gasto="Gasto", # Lo clasificamos como Gasto
                        costo=total_final,   # El monto que resta al balance
                        creado_por=request.user,
                        activo=True
                    )

                    messages.success(request, f"Sueldo registrado y descontado del balance: ${total_final}")
                    return redirect('dashboard')

            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Error del sistema: {e}")
    else:
        form = LiquidacionForm()

    return render(request, 'usuarios/registrar_sueldo.html', {'form': form})

@login_required
def liquidacion_pdf(request, liquidacion_id):
    # Obtener la liquidación específica
    liq = get_object_or_404(Liquidacion, id=liquidacion_id)
    
    # Contexto para el template
    context = {
        'liq': liq,
        'empleado': liq.empleado,
        'empresa': "Empresa S.A.",
    }
    
    # Renderizar PDF (igual que hicimos con el Balance)
    template_path = 'reportes/liquidacion_pdf.html'
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="liquidacion_{liq.empleado.username}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
       return HttpResponse('Error generando PDF')
    return response

@login_required
@user_passes_test(es_administrador)
def crear_trabajador_manual(request):
    if request.method == 'POST':
        form = CrearTrabajadorForm(request.POST)
        if form.is_valid():
            # 1. Crear instancia pero no guardar aún
            user = form.save(commit=False)
            
            # 2. BLOQUEO DE ACCESO: Esto hace imposible iniciar sesión
            user.set_unusable_password()
            
            user.save()

            # 3. Configurar Perfil y Valor Hora
            # El profile se crea por signal, lo actualizamos
            user.profile.creado_por = request.user
            user.profile.valor_hora = form.cleaned_data['valor_hora']
            user.profile.save()

            # 4. Asignar Grupo "Trabajador" (Lo creamos si no existe)
            grupo_trabajador, created = Group.objects.get_or_create(name='Trabajador')
            user.groups.add(grupo_trabajador)

            messages.success(request, f"Trabajador {user.first_name} registrado. (Sin acceso al sistema)")
            return redirect('dashboard')
    else:
        form = CrearTrabajadorForm()

    return render(request, 'usuarios/crear_trabajador.html', {'form': form})

@login_required
def generar_balance_pdf(request):
    # Restricción de acceso: Solo Administradores o Contadores
    if not (es_administrador(request.user) or request.user.groups.filter(name='Contador').exists()):
        return redirect('dashboard')

    # 1. Obtención de Datos Activos
    ingresos = Ingreso.objects.filter(activo=True).order_by('-fecha')
    egresos = Egreso.objects.filter(activo=True).order_by('-fecha')

    # 2. Cálculos de Totales Operativos
    total_ingresos = ingresos.aggregate(Sum('monto'))['monto__sum'] or 0
    total_egresos = egresos.aggregate(Sum('costo'))['costo__sum'] or 0
    
    # Utilidad antes de impuestos
    utilidad_operativa = total_ingresos - total_egresos

    # 3. Lógica Fiscal (Impuestos)
    TASA_IMPUESTO = 0.19  # Ejemplo: 19% de IVA o Renta
    impuesto_estimado = 0
    
    if utilidad_operativa > 0:
        impuesto_estimado = utilidad_operativa * TASA_IMPUESTO
    
    utilidad_neta = utilidad_operativa - impuesto_estimado
    estado = "Ganancia" if utilidad_neta >= 0 else "Pérdida"

    # 4. Preparación del PDF
    context = {
        'ingresos': ingresos,
        'egresos': egresos,
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
        'utilidad_operativa': utilidad_operativa,
        'tasa_impuesto_porcentaje': int(TASA_IMPUESTO * 100),
        'impuesto_estimado': impuesto_estimado,
        'utilidad_neta': utilidad_neta,
        'estado': estado,
        'generado_por': request.user.username,
        'empresa': "Empresa S.A."
    }

    template_path = 'reportes/balance_pdf.html'
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="balance_general.pdf"'

    template = get_template(template_path)
    html = template.render(context)

    # Crear el PDF con xhtml2pdf
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
       return HttpResponse('Error al generar el reporte PDF')
    return response

def solicitar_reset_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()
        
        if user:
            # Crear código
            cv = CodigoVerificacion.objects.create(usuario=user)
            cv.generar_codigo()
            
            # Enviar correo
            send_mail(
                'Código de Verificación - Empresa S.A.',
                f'Tu código de seguridad es: {cv.codigo}',
                'tu_correo@gmail.com',
                [email],
                fail_silently=False,
            )
            request.session['reset_email'] = email # Guardar en sesión para el siguiente paso
            return redirect('validar_codigo')
        else:
            messages.error(request, "Este correo no está registrado.")
    return render(request, 'solicitar_reset_password.html')

def validar_codigo(request):
    email = request.session.get('reset_email')
    if not email: return redirect('solicitar_reset_password')

    if request.method == 'POST':
        codigo_ingresado = request.POST.get('codigo')
        user = User.objects.get(email=email)
        cv = CodigoVerificacion.objects.filter(usuario=user, codigo=codigo_ingresado).last()

        if cv and cv.es_valido():
            cv.utilizado = True
            cv.save()
            request.session['codigo_validado'] = True
            return redirect('nueva_password')
        else:
            messages.error(request, "Código inválido o expirado.")
            
    return render(request, 'validar_codigo.html')

def nueva_password(request):
    if not request.session.get('codigo_validado'): return redirect('solicitar_reset_password')
    
    if request.method == 'POST':
        pass1 = request.POST.get('pass1')
        pass2 = request.POST.get('pass2')
        
        if pass1 == pass2:
            user = User.objects.get(email=request.session.get('reset_email'))
            user.password = make_password(pass1)
            user.save()
            # Limpiar sesión
            del request.session['reset_email']
            del request.session['codigo_validado']
            messages.success(request, "Contraseña actualizada correctamente.")
            return redirect('login')
        else:
            messages.error(request, "Las contraseñas no coinciden.")
            
    return render(request, 'nueva_password.html')

# views.py

@login_required
def generar_cotizacion(request):
    if request.method == 'POST':
        cliente = request.POST.get('cliente')
        horas = float(request.POST.get('horas', 0))
        # Usamos el valor hora del usuario que cotiza
        valor_h = float(request.user.profile.valor_hora) 
        
        productos_ids = request.POST.getlist('productos[]')
        cantidades = request.POST.getlist('cantidades[]')
        
        # 1. Crear la cabecera
        cotizacion = Cotizacion.objects.create(
            cliente_nombre=cliente,
            horas_estimadas=horas,
            valor_hora_aplicado=valor_h,
            descripcion_servicio=request.POST.get('descripcion'),
            creado_por=request.user
        )
        
        # 2. Procesar Items
        suma_materiales = 0
        for p_id, cant in zip(productos_ids, cantidades):
            prod = InventarioItem.objects.get(id=p_id)
            precio = prod.precio
            subtotal = precio * int(cant)
            suma_materiales += subtotal
            
            ItemCotizacion.objects.create(
                cotizacion=cotizacion,
                producto=prod,
                cantidad=int(cant),
                precio_unitario_momento=precio
            )
        
        # 3. Cálculo Final
        total_mano_obra = horas * valor_h
        cotizacion.total_materiales = suma_materiales
        cotizacion.total_cotizacion = total_mano_obra + suma_materiales
        cotizacion.save()
        
        return redirect('descargar_cotizacion_pdf', cotizacion_id=cotizacion.id)
        
    productos = InventarioItem.objects.all()
    return render(request, 'cotizaciones/crear_cotizacion.html', {'productos': productos})

@login_required
def descargar_cotizacion_pdf(request, cotizacion_id):
    # 1. Buscamos la cotización
    cotizacion = get_object_or_404(Cotizacion, id=cotizacion_id)
    
    # 2. Calculamos subtotales al vuelo para mostrarlos en el PDF
    for item in cotizacion.items.all():
        item.subtotal = item.cantidad * item.precio_unitario_momento

    context = {
        'cotizacion': cotizacion,
        'empresa': "Empresa S.A.",
        'fecha': timezone.now()
    }
    
    # 3. Renderizamos el PDF
    template_path = 'reportes/cotizacion_pdf.html'
    response = HttpResponse(content_type='application/pdf')
    # El nombre del archivo será "Cotizacion_5.pdf" por ejemplo
    response['Content-Disposition'] = f'inline; filename="Cotizacion_{cotizacion.id}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    # Creamos el PDF usando xhtml2pdf
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error al generar PDF')
    return response
@login_required
def editar_cliente(request, cliente_id):
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    cliente = get_object_or_404(Cliente, id=cliente_id)
    form = ClienteForm(request.POST or None, instance=cliente)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            return redirect('lista_clientes')

    return render(request, 'usuarios/editar_cliente.html', {
        'form': form,
        'cliente': cliente
    })
@login_required
def eliminar_cliente(request, cliente_id):
    if not (request.user.groups.filter(name='Administrador').exists() or request.user.is_superuser):
        return redirect('dashboard')

    cliente = get_object_or_404(Cliente, id=cliente_id)

    if request.method == "POST":
        cliente.delete()
        return redirect('lista_clientes')

    return render(request, 'usuarios/eliminar_cliente.html', {
        'cliente': cliente
    })