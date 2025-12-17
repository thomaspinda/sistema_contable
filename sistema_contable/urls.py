"""
URL configuration for sistema_contable project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from contabilidad import views

urlpatterns = [
    # Admin de Django (Para el Superuser)
    path('admin/', admin.site.urls),
    
    # Dashboard (Página principal)
    path('', views.dashboard, name='dashboard'),

    # Gestión de Empleados (Solo Admin)
    path('crear-empleado/', views.crear_empleado, name='crear_empleado'),

    # Autenticación (Login / Logout)
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Aquí irán las futuras URLs de operación
    # path('inventario/', views.registrar_item, name='registrar_item'),
    # INGRESOS
  path('ingresos/', views.ingresos_page, name='ingresos_page'),

    # Egresos
    path('egresos/', views.egresos_page, name='egresos_page'),

    # Inventario
    path('inventarios/', views.inventario_page, name='inventario_page'),
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/editar/<int:user_id>/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/eliminar/<int:user_id>/', views.eliminar_usuario, name='eliminar_usuario'),
    path('usuarios/solicitud/<int:solicitud_id>/atendida/', views.marcar_solicitud_atendida, name='marcar_solicitud_atendida'),
    path("password/solicitar/", views.solicitar_reset_password, name="solicitar_reset_password"),

    path("movimientos/editar/<str:movimiento_tipo>/<int:movimiento_id>/", views.editar_movimiento, name="editar_movimiento"),
    path("movimientos/eliminar/<str:movimiento_tipo>/<int:movimiento_id>/", views.eliminar_movimiento, name="eliminar_movimiento"),

    path("inventarios/editar/<int:item_id>/", views.editar_item_inventario, name="editar_item"),
    path("inventarios/eliminar/<int:item_id>/", views.eliminar_item_inventario, name="eliminar_item"),
    path('clientes/registrar/', views.registrar_cliente, name='registrar_cliente'),
    path('clientes/', views.lista_clientes, name='lista_clientes'),
    path('inventario/nuevo-catalogo/', views.crear_item_catalogo, name='crear_item_catalogo'),
    path('personal/pagar-sueldo/', views.registrar_sueldo, name='registrar_sueldo'),
    path('reportes/liquidacion/<int:liquidacion_id>/', views.liquidacion_pdf, name='liquidacion_pdf'),
    path('personal/nuevo-trabajador/', views.crear_trabajador_manual, name='crear_trabajador_manual'),
    path('reportes/balance/', views.generar_balance_pdf, name='generar_balance_pdf'),
    path('reset-password/', views.solicitar_reset_password, name='solicitar_reset_password'),
    path('reset-password/validar/', views.validar_codigo, name='validar_codigo'),
    path('reset-password/nueva/', views.nueva_password, name='nueva_password'),
    path('cotizaciones/nueva/', views.generar_cotizacion, name='generar_cotizacion'),
    path('cotizaciones/pdf/<int:cotizacion_id>/', views.descargar_cotizacion_pdf, name='descargar_cotizacion_pdf'),
    path('clientes/editar/<int:cliente_id>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/eliminar/<int:cliente_id>/', views.eliminar_cliente, name='eliminar_cliente'),
]