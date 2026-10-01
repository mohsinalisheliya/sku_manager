# sku_manager/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('', views.sku_generate, name='sku_generate'),
    path('inventory/', views.sku_inventory, name='sku_inventory'),
    path('edit/<int:pk>/', views.sku_edit, name='sku_edit'),
    path('delete/<int:pk>/', views.sku_delete, name='sku_delete'),
    path('toggle-listed/<int:pk>/', views.toggle_listed, name='sku_toggle_listed'),
    path('stock/<int:pk>/<str:action>/', views.adjust_stock, name='sku_adjust_stock'),
    path('platforms/', views.platform_manager, name='platform_manager'),
    path('platforms/delete/<int:pk>/', views.platform_delete, name='platform_delete'),
    path('export-csv/', views.export_csv, name='sku_export_csv'),

    # Dynamic Storage Boxes
    path('boxes/', views.box_manager, name='box_manager'),
    path('boxes/delete/<int:pk>/', views.box_delete, name='box_delete'),

    # QR Scanner & Dispatch
    path('scanner/', views.sku_scanner, name='sku_scanner'),
    path('qr/download/<int:pk>/', views.sku_qr_download, name='sku_qr_download'),
    path('print-label/<int:pk>/', views.sku_print_label, name='sku_print_label'),
    path('dispatch/<str:sku>/', views.scan_dispatch, name='scan_dispatch'),
    path('dispatch-logs/', views.dispatch_logs, name='dispatch_logs'),

    # sku_manager/urls.py me add karein:
path('settings/', views.app_settings_view, name='app_settings'),
]