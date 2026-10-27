from django.core.management.base import BaseCommand
from django.db.models import Q

from app1.models import WhatsAppNotification
from app1.whatsapp import notify_doctor_of_booking


class Command(BaseCommand):
	help = 'Retry unsent appointment WhatsApp notifications when the 24-hour window is open.'

	def handle(self, *args, **options):
		retryable = WhatsAppNotification.objects.filter(status__in=(
			WhatsAppNotification.Status.PENDING,
			WhatsAppNotification.Status.SKIPPED,
		)).select_related('inquiry')
		retryable = list(retryable) + list(
			WhatsAppNotification.objects.filter(
				Q(last_reason__startswith='http_400')
				| Q(last_reason__startswith='http_401')
				| Q(last_reason__startswith='http_429')
				| Q(last_reason__startswith='http_500')
				| Q(last_reason__startswith='http_502')
				| Q(last_reason__startswith='http_503')
				| Q(last_reason__startswith='http_504'),
				status=WhatsAppNotification.Status.FAILED,
			).select_related('inquiry')
		)
		for notification in retryable:
			notify_doctor_of_booking(notification.inquiry)
		self.stdout.write(self.style.SUCCESS(f'Checked {len(retryable)} WhatsApp notification(s).'))
