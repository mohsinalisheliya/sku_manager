# sku_manager/urls.py
from django.urls import path
from . import views

# sku_manager/urls.py
urlpatterns = [
    # Auth
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Product master and stock management
    path('products/', views.product_master, name='product_master'),
    path('products/add/', views.product_master, name='product_create'),
    path('products/edit/<int:pk>/', views.product_edit_details, name='product_edit_details'),
    path('products/<int:pk>/edit-details/', views.product_edit_details, name='product_edit_details_legacy'),
    path('stock/manage/add/', views.stock_manage_view, name='stock_manage_create'),
    path('inventory/<int:pk>/stock/', views.stock_action, name='stock_action'),
    path('inventory/<int:pk>/stock-action/', views.stock_action, name='stock_action_legacy'),
    path('', views.inventory_list, name='inventory_list'),
    path('inventory/', views.inventory_list, name='sku_inventory'),
    path('inventory-list/', views.inventory_list, name='inventory_list_legacy'),
    path('stock-list/', views.stock_inventory_list, name='stock_inventory_list'),
    path('stock/edit/<int:pk>/', views.stock_manage_view, name='stock_edit'),
    path('products/<int:pk>/detail/', views.product_stock_detail, name='product_stock_detail'),
    path('products/<int:pk>/batches/', views.product_batches_view, name='product_batches'),
    path('products/<int:pk>/batches/add/', views.add_batch_action, name='add_batch_action'),
    path('products/<int:pk>/batches/add/', views.add_batch_action, name='product_batch_add'),
    path('stock/batch/<int:batch_id>/edit/', views.edit_batch_action, name='edit_batch_action'),
    path('products/<int:pk>/toggle-sales/', views.toggle_product_sales, name='toggle_product_sales'),
    
    # Inward Stock & Batches
    path('stock/add/', views.stock_inward, name='stock_inward'),

    # Existing Catalog & Operations
    path('edit/<int:pk>/', views.sku_edit, name='sku_edit'),
    path('delete/<int:pk>/', views.sku_delete, name='sku_delete'),
    path('toggle-listed/<int:pk>/', views.toggle_listed, name='sku_toggle_listed'),
    path('stock/<int:pk>/<str:action>/', views.adjust_stock, name='sku_adjust_stock'),
    path('platforms/', views.platform_manager, name='platform_manager'),
    path('platforms/delete/<int:pk>/', views.platform_delete, name='platform_delete'),
    path('boxes/', views.box_manager, name='box_manager'),
    path('boxes/delete/<int:pk>/', views.box_delete, name='box_delete'),
    path('settings/', views.app_settings_view, name='app_settings'),
    path('export-csv/', views.export_csv, name='sku_export_csv'),
    path('scanner/', views.sku_scanner, name='sku_scanner'),
    path('qr/download/<int:pk>/', views.sku_qr_download, name='sku_qr_download'),
    path('print-label/<int:pk>/', views.sku_print_label, name='sku_print_label'),
    path('dispatch/<str:sku>/', views.scan_dispatch, name='scan_dispatch'),
    path('dispatch-logs/', views.dispatch_logs, name='dispatch_logs'),
]