from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('products/', views.products, name='products'),
    path('products/<int:pk>/units/add/', views.unit_add, name='unit_add'),
    path('units/<int:pk>/update/', views.unit_update, name='unit_update'),
    path('units/<int:pk>/delete/', views.unit_delete, name='unit_delete'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/new/', views.order_create, name='order_create'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/edit/', views.order_edit, name='order_edit'),
    path('orders/<int:pk>/delete/', views.order_delete, name='order_delete'),
    path('orders/<int:pk>/receive/', views.receive_batch, name='receive_batch'),
    path('batches/<int:pk>/prep/add/', views.prep_add, name='prep_add'),
    path('preps/<int:pk>/delete/', views.prep_delete, name='prep_delete'),
    path('sell/', views.sell, name='sell'),
    path('sales/record/', views.sale_record, name='sale_record'),
    path('sales/<int:pk>/delete/', views.sale_delete, name='sale_delete'),
    path('layby/', views.layby_list, name='layby'),
    path('layby/<int:pk>/settle/', views.layby_settle, name='layby_settle'),
    path('summary/', views.summary, name='summary'),
]