from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Location(models.Model):
	name = models.CharField(max_length=255, unique=True)

	def __str__(self):
		return self.name


class Treatment(models.Model):
	name = models.CharField(max_length=150, unique=True)
	description = models.TextField(blank=True, default='')
	image = models.ImageField(upload_to='treatments/', blank=True, null=True)

	@property
	def url_slug(self):
		return slugify(self.name) or f'treatment-{self.pk}'

	def __str__(self):
		return self.name


class PatientInquiry(models.Model):
	class Status(models.TextChoices):
		NEW = 'new', 'New'
		SCHEDULED = 'scheduled', 'Scheduled'
		COMPLETED = 'completed', 'Completed'
		CANCELLED = 'cancelled', 'Cancelled'

	treatment = models.ForeignKey(
		'Treatment',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='inquiries',
	)
	full_name = models.CharField(max_length=150)
	phone_number = models.CharField(max_length=20, db_index=True)
	email = models.EmailField()
	whatsapp_consent = models.BooleanField(default=False)
	location = models.ForeignKey(
		'Location',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='inquiries',
	)
	problems = models.TextField(blank=True, default='')
	appointment_date = models.DateField(null=True, blank=True)
	appointment_time = models.TimeField(null=True, blank=True)
	status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
	created_at = models.DateTimeField(default=timezone.now, editable=False)

	@property
	def booking_number(self):
		return f'PT-{self.pk:05d}'

	def __str__(self):
		return self.full_name


class PatientBill(models.Model):
	class Status(models.TextChoices):
		ISSUED = 'issued', 'Issued'
		PAID = 'paid', 'Paid'
		VOID = 'void', 'Void'

	inquiry = models.ForeignKey(
		PatientInquiry,
		on_delete=models.PROTECT,
		related_name='bills',
	)
	service_description = models.CharField(max_length=200)
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	notes = models.TextField(blank=True)
	status = models.CharField(max_length=10, choices=Status.choices, default=Status.ISSUED)
	created_at = models.DateTimeField(auto_now_add=True)

	@property
	def bill_number(self):
		return f'PTB-{self.created_at:%Y}-{self.pk:06d}'

	def __str__(self):
		return self.bill_number


class ContactQuery(models.Model):
	class Status(models.TextChoices):
		NEW = 'new', 'New'
		REVIEWED = 'reviewed', 'Reviewed'
		CLOSED = 'closed', 'Closed'

	first_name = models.CharField(max_length=100)
	last_name = models.CharField(max_length=100)
	phone_number = models.CharField(max_length=20)
	message = models.TextField()
	agree = models.BooleanField(default=False)
	status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.first_name} {self.last_name}"

class WhatsAppConversation(models.Model):
	inquiry = models.ForeignKey(
		PatientInquiry, on_delete=models.SET_NULL, null=True, blank=True,
		related_name='whatsapp_conversations',
	)
	phone_number = models.CharField(max_length=20, unique=True, db_index=True)
	last_inbound_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.phone_number


class WhatsAppMessage(models.Model):
	conversation = models.ForeignKey(
		WhatsAppConversation, on_delete=models.CASCADE, related_name='messages'
	)
	message_id = models.CharField(max_length=255, unique=True)
	direction = models.CharField(max_length=8, choices=(('inbound', 'Inbound'), ('outbound', 'Outbound')))
	message_type = models.CharField(max_length=40, blank=True)
	body = models.TextField(blank=True)
	wa_timestamp = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at']

	def __str__(self):
		return f'{self.direction} {self.message_id}'


class WhatsAppNotification(models.Model):
	class Status(models.TextChoices):
		PENDING = 'pending', 'Pending'
		SENT = 'sent', 'Sent'
		FAILED = 'failed', 'Failed'
		SKIPPED = 'skipped', 'Skipped'

	inquiry = models.OneToOneField(
		PatientInquiry, on_delete=models.CASCADE, related_name='whatsapp_notification'
	)
	status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
	attempts = models.PositiveSmallIntegerField(default=0)
	last_reason = models.CharField(max_length=80, blank=True)
	updated_at = models.DateTimeField(auto_now=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f'{self.inquiry.booking_number}: {self.status}'


class WebContacts(models.Model):
	mobile_number = models.CharField(max_length=20)
	gmail = models.EmailField()

	def __str__(self):
		return self.mobile_number
