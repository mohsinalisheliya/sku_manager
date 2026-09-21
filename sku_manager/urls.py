# sku_manager/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.sku_generate, name='sku_generate'),
    path('inventory/', views.sku_inventory, name='sku_inventory'),
    path('edit/<int:pk>/', views.sku_edit, name='sku_edit'),
    path('delete/<int:pk>/', views.sku_delete, name='sku_delete'),
    path('toggle-listed/<int:pk>/', views.toggle_listed, name='sku_toggle_listed'),
    path('stock/<int:pk>/<str:action>/', views.adjust_stock, name='sku_adjust_stock'), # <-- Updated to <str:action>
    path('export-csv/', views.export_csv, name='sku_export_csv'),
]