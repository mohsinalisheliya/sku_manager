import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Q
from .models import JewelrySKU

def get_next_serial():
    latest = JewelrySKU.objects.order_by('-id').first()
    if not latest:
        return '001'
    try:
        return str(int(latest.number) + 1).zfill(3)
    except (ValueError, TypeError):
        return '001'

def sku_dashboard(request):
    search_query = request.GET.get('q', '').strip()
    skus = JewelrySKU.objects.all()

    if search_query:
        skus = skus.filter(
            Q(sku__icontains=search_query) |
            Q(name__icontains=search_query) |
            Q(style__icontains=search_query) |
            Q(category__icontains=search_query)
        )

    if request.method == 'POST':
        category = request.POST.get('category', '').strip()
        style = request.POST.get('style', '').strip()
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '').strip()
        size = request.POST.get('size', '').strip()
        number = request.POST.get('number', '').strip()

        try:
            item = JewelrySKU(
                category=category,
                style=style,
                name=name,
                color=color,
                size=size,
                number=number
            )
            item.save()
            messages.success(request, f"SKU '{item.sku}' successfully saved!")
            return redirect('sku_dashboard')
        except Exception:
            messages.error(request, "Error saving SKU. It might already exist in your database.")

    return render(request, 'sku_manager/index.html', {
        'skus': skus,
        'search_query': search_query,
        'is_edit': False,
        'next_serial': get_next_serial(),
    })

def sku_edit(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    
    if request.method == 'POST':
        item.category = request.POST.get('category', '').strip()
        item.style = request.POST.get('style', '').strip()
        item.name = request.POST.get('name', '').strip()
        item.color = request.POST.get('color', '').strip()
        item.size = request.POST.get('size', '').strip()
        item.number = request.POST.get('number', '').strip()

        try:
            item.save()
            messages.success(request, f"SKU updated to '{item.sku}'!")
            return redirect('sku_dashboard')
        except Exception:
            messages.error(request, "Error updating. Make sure new SKU does not conflict.")

    skus = JewelrySKU.objects.all()
    return render(request, 'sku_manager/index.html', {
        'skus': skus,
        'is_edit': True,
        'edit_item': item,
    })

def sku_delete(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    sku_val = item.sku
    item.delete()
    messages.info(request, f"SKU '{sku_val}' deleted.")
    return redirect('sku_dashboard')

def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jewelry_skus.csv"'

    writer = csv.writer(response)
    writer.writerow(['SKU', 'Category', 'Style', 'Name', 'Color', 'Size', 'Number', 'Created At'])

    for obj in JewelrySKU.objects.all():
        writer.writerow([
            obj.sku, obj.category, obj.style, obj.name,
            obj.color, obj.size, obj.number,
            obj.created_at.strftime("%Y-%m-%d %H:%M")
        ])

    return response

# Add this function to sku_manager/views.py

def toggle_listed(request, pk):
    item = get_object_or_404(JewelrySKU, pk=pk)
    item.is_listed = not item.is_listed
    item.save(update_fields=['is_listed', 'updated_at'])
    messages.success(
        request, 
        f"SKU '{item.sku}' marked as {'Listed ✓' if item.is_listed else 'Unlisted'}."
    )
    return redirect(request.META.get('HTTP_REFERER', 'sku_dashboard'))