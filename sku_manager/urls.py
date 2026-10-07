# sku_manager/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # sku_manager/urls.py ke urlpatterns me add karein:

    # Part 1: Product Master, Listing & Secure Delete
# sku_manager/urls.py ke urlpatterns me:

    # Unified Product Master (Handles both Add & Edit)
    path('products/', views.product_master, name='product_master'),
    path('products/edit/<int:pk>/', views.product_master, name='product_edit_details'),
    path('products/list/', views.product_list_view, name='product_list'),
    path('products/delete/<int:pk>/', views.product_delete_secure, name='product_delete_secure'),
    # Part 2: Inventory & Stock Management
    path('', views.inventory_list, name='inventory_list'),
    path('inventory/', views.inventory_list, name='sku_inventory'), # Alias for compatibility
    path('inventory/stock/<int:pk>/', views.stock_action, name='stock_action'),

    # Backward-compatible generator aliases
    path('generate/', views.product_master, name='sku_generate'),
    path('stock-list/', views.inventory_list, name='stock_inventory_list'),

    # Storage Units & Channels
    path('boxes/', views.box_manager, name='box_manager'),
    path('boxes/delete/<int:pk>/', views.box_delete, name='box_delete'),
    path('platforms/', views.platform_manager, name='platform_manager'),
    path('platforms/delete/<int:pk>/', views.platform_delete, name='platform_delete'),

    # Settings & CSV
    path('settings/', views.app_settings_view, name='app_settings'),
    path('export-csv/', views.export_csv, name='sku_export_csv'),

    # Scanner, QR Download & Dispatch
    path('scanner/', views.sku_scanner, name='sku_scanner'),
    path('print-label/<int:pk>/', views.sku_print_label, name='sku_print_label'),
    path('qr/<int:pk>/download/', views.sku_qr_download, name='sku_qr_download'),
    path('dispatch/<str:sku>/', views.scan_dispatch, name='scan_dispatch'),
    path('dispatch-logs/', views.dispatch_logs, name='dispatch_logs'),
]