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
    path('inventario/', views.inventario_page, name='inventario_page'),
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/editar/<int:user_id>/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/eliminar/<int:user_id>/', views.eliminar_usuario, name='eliminar_usuario'),
    path('usuarios/solicitud/<int:solicitud_id>/atendida/', views.marcar_solicitud_atendida, name='marcar_solicitud_atendida'),
    path("password/solicitar/", views.solicitar_reset_password, name="solicitar_reset_password"),

]