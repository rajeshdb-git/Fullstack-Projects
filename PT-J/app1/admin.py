from django.contrib import admin

from .models import (
    ContactQuery,
    Location,
    PatientBill,
    PatientInquiry,
    Treatment,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppNotification,
)


@admin.register(PatientInquiry)
class PatientInquiryAdmin(admin.ModelAdmin):
    list_display = (
        'booking_number',
        'full_name',
        'phone_number',
        'treatment',
        'status',
        'appointment_date',
        'created_at',
    )
    list_filter = ('status', 'location', 'treatment')
    search_fields = ('full_name', 'phone_number', 'email')


@admin.register(PatientBill)
class PatientBillAdmin(admin.ModelAdmin):
    list_display = ('id', 'inquiry', 'amount', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    search_fields = ('name',)


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name', 'description')


@admin.register(ContactQuery)
class ContactQueryAdmin(admin.ModelAdmin):
    list_display = (
        'first_name',
        'last_name',
        'phone_number',
        'status',
        'created_at',
    )
    list_filter = ('status',)
    search_fields = ('first_name', 'last_name', 'phone_number', 'message')


@admin.register(WhatsAppConversation)
class WhatsAppConversationAdmin(admin.ModelAdmin):
	list_display = ('phone_number', 'last_inbound_at', 'updated_at')
	search_fields = ('phone_number',)


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
	list_display = ('conversation', 'direction', 'message_type', 'created_at')
	search_fields = ('conversation__phone_number', 'body')
	readonly_fields = ('message_id', 'conversation', 'direction', 'message_type', 'body', 'wa_timestamp', 'created_at')


@admin.register(WhatsAppNotification)
class WhatsAppNotificationAdmin(admin.ModelAdmin):
	list_display = ('inquiry', 'status', 'attempts', 'last_reason', 'updated_at')
	list_filter = ('status',)
	readonly_fields = ('inquiry', 'status', 'attempts', 'last_reason', 'created_at', 'updated_at')
