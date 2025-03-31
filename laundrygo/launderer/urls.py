from django.urls import path
from . import views

app_name = 'launderer'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.launderer_login, name='login'),
    path('logout/', views.launderer_logout, name='logout'),
    path('register/', views.launderer_register, name='register'),
    path('received-orders/', views.received_orders, name='received_orders'),
    path('pending-orders/', views.pending_orders, name='pending_orders'),
    path('completed-orders/', views.completed_orders, name='completed_orders'),
    path('rejected-orders/', views.rejected_orders, name='rejected_orders'),
    path('order/<uuid:order_id>/', views.order_detail, name='order_detail'),
    path('order/<uuid:order_id>/confirm/', views.confirm_order, name='confirm_order'),
    path('order/<uuid:order_id>/reject/', views.reject_order, name='reject_order'),
    path('settings/', views.settings, name='settings'),
    path('manage-payment-methods/', views.manage_payment_methods, name='manage_payment_methods'),
    path('delete-payment-method/<int:payment_id>/', views.delete_payment_method, name='delete_payment_method'),
    path('manage-working-hours/', views.manage_working_hours, name='manage_working_hours'),
    path('manage-services/', views.manage_services, name='manage_services'),
    path('edit-service/<int:service_id>/', views.edit_service, name='edit_service'),
    path('delete-service/<int:service_id>/', views.delete_service, name='delete_service'),
    path('manage-cloth-items/', views.manage_cloth_items, name='manage_cloth_items'),
    path('edit-cloth-item/<int:item_id>/', views.edit_cloth_item, name='edit_cloth_item'),
    path('delete-cloth-item/<int:item_id>/', views.delete_cloth_item, name='delete_cloth_item'),
    path('help-support/', views.help_support, name='help_support'),
    path('notifications/', views.notifications, name='notifications'),
    path('mark-notification-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
]

