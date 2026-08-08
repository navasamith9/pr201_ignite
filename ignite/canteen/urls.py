from django.urls import path

from . import views

app_name = 'canteen'

urlpatterns = [
    path('', views.menu, name='menu'),
    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/', views.update_cart, name='update_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('order/place/', views.place_order, name='place_order'),
    path('orders/<int:order_id>/checkout/', views.checkout_order, name='checkout_order'),
    path('orders/<int:order_id>/payment-success/', views.payment_success, name='payment_success'),
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('staff/menu/', views.staff_menu, name='staff_menu'),
    path('staff/menu/add/', views.staff_menu_edit, name='staff_menu_add'),
    path('staff/menu/<int:item_id>/edit/', views.staff_menu_edit, name='staff_menu_edit'),
    path('staff/menu/<int:item_id>/toggle/', views.toggle_item_availability, name='toggle_item_availability'),
    path('staff/menu/<int:item_id>/delete/', views.delete_menu_item, name='delete_menu_item'),
    path('staff/orders/', views.staff_orders, name='staff_orders'),
    path('staff/orders/<int:order_id>/status/', views.update_order_status, name='update_order_status'),
]
