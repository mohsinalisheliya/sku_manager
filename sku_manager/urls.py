Step 3: Register Clean URLs in sku_manager/urls.py
Python
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Part 1: Product Master & Detail Edit
    path('products/', views.product_master, name='product_master'),
    path('products/edit/<int:pk>/', views.product_edit_details, name='product_edit_details'),

    # Part 2: Inventory & Stock Management
    path('', views.inventory_list, name='inventory_list'),
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/stock/<int:pk>/', views.stock_action, name='stock_action'),

    # Utility Views
    path('boxes/', views.box_manager, name='box_manager'),
    path('boxes/delete/<int:pk>/', views.box_delete, name='box_delete'),
    path('platforms/', views.platform_manager, name='platform_manager'),
    path('platforms/delete/<int:pk>/', views.platform_delete, name='platform_delete'),
    path('settings/', views.app_settings_view, name='app_settings'),
    path('scanner/', views.sku_scanner, name='sku_scanner'),
    path('print-label/<int:pk>/', views.sku_print_label, name='sku_print_label'),
    path('dispatch/<str:sku>/', views.scan_dispatch, name='scan_dispatch'),
    path('dispatch-logs/', views.dispatch_logs, name='dispatch_logs'),
]