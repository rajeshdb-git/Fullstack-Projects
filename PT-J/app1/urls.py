from django.urls import path
from . import views

urlpatterns = [
    path('', views.home),
    path('home/', views.home, name='home'),
    
    path('contact/', views.contact, name='contact'),
    path('booking-status/', views.booking_status, name='booking_status'),
    path('appointment/', views.appointment, name='appointment'),
    path('webhooks/whatsapp/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('services/treatment/<int:treatment_id>/', views.legacy_treatment_detail, name='legacy_treatment_detail'),
    path('services/<slug:treatment_slug>-<int:treatment_id>/', views.treatment_detail, name='treatment_detail'),
    path('services/<slug:service>/', views.service_page, name='service_page'),
    path('about/', views.about, name='about'),
    path('all-conditions/', views.all_conditions, name='all_conditions'),
    path('doctor/login/', views.doctor_login, name='doctor_login'),
    path('doctor/logout/', views.doctor_logout, name='doctor_logout'),
    path('doctor/generate-treatment-description/', views.doctor_generate_treatment_description, name='doctor_generate_treatment_description'),
    path('doctor/catalog/', views.doctor_catalog, name='doctor_catalog'),
    path('doctor/bookings/', views.doctor_bookings, name='doctor_bookings'),
    path('doctor/inquiries/', views.doctor_inquiries, name='doctor_inquiries'),
    path('doctor/whatsapp/', views.doctor_whatsapp_inbox, name='doctor_whatsapp_inbox'),
    path('doctor/bookings/<int:booking_id>/', views.doctor_booking_detail, name='doctor_booking_detail'),
    path('doctor/bills/<int:bill_id>/', views.doctor_bill_detail, name='doctor_bill_detail'),
    path(
    "doctor/update-contact/",
    views.update_web_contacts,
    name="update_web_contacts",
),
]
