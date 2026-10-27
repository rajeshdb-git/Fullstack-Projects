import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone as dt_timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone
from dotenv import dotenv_values

from .models import (
	PatientInquiry, WhatsAppConversation, WhatsAppMessage, WhatsAppNotification,
)

logger = logging.getLogger(__name__)


def _doctor_name_from_env():
	"""Read the current .env value so a long-running server can't retain an old name."""
	env_file = settings.BASE_DIR / '.env'
	try:
		env_value = dotenv_values(env_file).get('WHATSAPP_DOCTOR_NAME')
	except OSError:
		env_value = None
	return env_value if env_value is not None else settings.WHATSAPP_DOCTOR_NAME


def _message_value(value, fallback='Not provided', limit=300):
	text = re.sub(r'\s+', ' ', str(value or '')).strip()
	return text[:limit] if text else fallback


def normalize_phone(phone_number):
	digits = re.sub(r'\D', '', phone_number or '')
	if digits.startswith('00'):
		return digits[2:]
	if len(digits) == 10:
		return f'{settings.WHATSAPP_DEFAULT_COUNTRY_CODE}{digits}'
	if digits.startswith('0'):
		return digits[1:]
	return digits


def send_template(recipient, template_name, body, opener=None):
	opener = opener or urlopen
	if not settings.WHATSAPP_ENABLED:
		return False, 'disabled'
	if not settings.WHATSAPP_ACCESS_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
		return False, 'incomplete_configuration'
	if not re.fullmatch(r'[1-9]\d{7,14}', recipient or ''):
		return False, 'invalid_recipient_number'
	if not template_name or not settings.WHATSAPP_TEMPLATE_LANGUAGE:
		return False, 'template_not_configured'

	payload = {
		'messaging_product': 'whatsapp',
		'recipient_type': 'individual',
		'to': recipient,
		'type': 'template',
		'template': {
			'name': template_name,
			'language': {'code': settings.WHATSAPP_TEMPLATE_LANGUAGE},
			'components': [{
				'type': 'body',
				'parameters': [{
					'type': 'text',
					'text': _format_template_parameter(body),
				}],
			}],
		},
	}
	request = Request(
		f'https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/'
		f'{settings.WHATSAPP_PHONE_NUMBER_ID}/messages',
		data=json.dumps(payload).encode('utf-8'),
		headers={
			'Authorization': f'Bearer {settings.WHATSAPP_ACCESS_TOKEN}',
			'Content-Type': 'application/json',
		},
		method='POST',
	)
	try:
		with opener(request, timeout=10) as response:
			try:
				result = json.loads(response.read().decode('utf-8'))
			except (AttributeError, TypeError, UnicodeDecodeError, ValueError):
				result = {}
		return True, result.get('messages', [{}])[0].get('id', '')
	except HTTPError as error:
		return False, _record_api_error(error, 'template')
	except (URLError, TimeoutError, OSError, ValueError) as error:
		logger.warning('WhatsApp template request failed (%s).', type(error).__name__)
		return False, 'transport_error'


def _format_template_parameter(body):
	text = str(body or '').replace('\r\n', '\n').replace('\r', '\n')
	text = ''.join(
		character for character in text
		if character == '\n' or character == '\t'
		or (ord(character) >= 32 and ord(character) != 127)
	)
	lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n')]
	sections = []
	current_section = []
	for line in lines:
		if line:
			current_section.append(line)
		elif current_section:
			sections.append(current_section)
			current_section = []
	if current_section:
		sections.append(current_section)
	section_separator = '  \u2501\u2501\u2501  '
	formatted_sections = ['  \u2022  '.join(section) for section in sections]
	return section_separator.join(formatted_sections).strip()[:1000]


def _record_api_error(error, operation):
	try:
		error_details = json.loads(error.read().decode('utf-8')).get('error', {})
	except (AttributeError, TypeError, UnicodeDecodeError, ValueError):
		error_details = {}
	meta_code = error_details.get('code')
	meta_subcode = error_details.get('error_subcode')
	logger.warning(
		'WhatsApp %s request returned HTTP %s (Meta code %s, subcode %s).',
		operation,
		error.code,
		meta_code if isinstance(meta_code, int) else 'unavailable',
		meta_subcode if isinstance(meta_subcode, int) else 'unavailable',
	)
	reason = f'http_{error.code}'
	if isinstance(meta_code, int):
		reason += f'_meta_{meta_code}'
	if isinstance(meta_subcode, int):
		reason += f'_{meta_subcode}'
	return reason[:80]


def notify_doctor_of_booking(inquiry):
	notification, _ = WhatsAppNotification.objects.get_or_create(inquiry=inquiry)
	if notification.status == WhatsAppNotification.Status.SENT:
		return True

	doctor_number = normalize_phone(settings.WHATSAPP_DOCTOR_NUMBER)
	if not settings.WHATSAPP_ENABLED:
		notification.status = WhatsAppNotification.Status.SKIPPED
		notification.last_reason = 'disabled'
		notification.save(update_fields=['status', 'last_reason', 'updated_at'])
		return False
	if not doctor_number:
		notification.status = WhatsAppNotification.Status.FAILED
		notification.last_reason = 'invalid_doctor_number'
		notification.save(update_fields=['status', 'last_reason', 'updated_at'])
		return False

	if not settings.WHATSAPP_APPOINTMENT_TEMPLATE:
		notification.status = WhatsAppNotification.Status.FAILED
		notification.last_reason = 'template_not_configured'
		notification.save(update_fields=['status', 'last_reason', 'updated_at'])
		return False

	treatment = _message_value(inquiry.treatment.name if inquiry.treatment else '')
	location = _message_value(inquiry.location.name if inquiry.location else '')
	appointment_date = inquiry.appointment_date.strftime('%d %b %Y') if inquiry.appointment_date else 'Not scheduled'
	appointment_time = timezone.localtime(
		timezone.make_aware(timezone.datetime.combine(inquiry.appointment_date, inquiry.appointment_time))
	).strftime('%I:%M %p') if inquiry.appointment_date and inquiry.appointment_time else 'Not scheduled'
	doctor_name = _message_value(_doctor_name_from_env(), fallback='', limit=60)
	doctor_name = re.sub(
		r'^(?:(?:dr|doctor)\.?\s*)+', '', doctor_name, flags=re.IGNORECASE
	).strip()
	greeting = f'Hello Dr. {doctor_name},' if doctor_name else 'Hello Doctor,'
	patient_phone = normalize_phone(inquiry.phone_number)
	if patient_phone.startswith('91') and len(patient_phone) == 12:
		patient_phone = f'+91 {patient_phone[2:7]} {patient_phone[7:]}'
	else:
		patient_phone = f'+{patient_phone}' if patient_phone else 'Not provided'
	reason = _message_value(inquiry.problems, limit=280)
	received_at = timezone.localtime(inquiry.created_at).strftime('%d %b %Y, %I:%M %p')
	status_labels = {
		PatientInquiry.Status.NEW: '\U0001F7E0 Pending Confirmation',
		PatientInquiry.Status.SCHEDULED: '\U0001F7E2 Confirmed',
		PatientInquiry.Status.COMPLETED: '\u2705 Completed',
		PatientInquiry.Status.CANCELLED: '\U0001F534 Cancelled',
	}
	status_label = status_labels.get(inquiry.status, '\U0001F7E0 Pending Confirmation')
	appointment_slot = (
		f'{appointment_date} at {appointment_time}'
		if inquiry.appointment_date and inquiry.appointment_time
		else '\u23F3 Not Scheduled'
	)
	body = '\n'.join((
		f'Appointment ID: {inquiry.booking_number}',
		f'Status: {status_label}',
		'',
		f'\U0001F468\u200d\u2695\ufe0f {greeting}',
		'',
		'You have received a new appointment request.',
		'',
		'\U0001F464 PATIENT DETAILS',
		f'Name: {_message_value(inquiry.full_name, limit=100)}',
		f'Phone: {patient_phone}',
		f'Email: {_message_value(inquiry.email, limit=120)}',
		'',
		'\U0001F5D3\ufe0f APPOINTMENT DETAILS',
		f'Date & Time: {appointment_slot}',
		f'Concern: {_message_value(treatment, limit=80)}',
		f'Location: {_message_value(location, limit=80)}',
		f"Patient's Reason: {_message_value(reason, limit=140)}",
		'',
		'\U0001F4E5 Request Received:',
		received_at,
		'',
		'\u26A0\ufe0f ACTION REQUIRED',
		'Please review the request and contact the patient to confirm a suitable date and time.',
		'',
		'\U0001F449 Open your Doctor Dashboard to review and schedule this request.',
		'',
		'Thank you.',
	))
	notification.attempts += 1
	sent, result = send_template(
		doctor_number, settings.WHATSAPP_APPOINTMENT_TEMPLATE, body
	)
	notification.status = WhatsAppNotification.Status.SENT if sent else WhatsAppNotification.Status.FAILED
	notification.last_reason = 'approved_template' if sent else result
	notification.save(update_fields=['status', 'attempts', 'last_reason', 'updated_at'])
	if sent:
		conversation, _ = WhatsAppConversation.objects.get_or_create(phone_number=doctor_number)
		if result:
			WhatsAppMessage.objects.get_or_create(
				message_id=result,
				defaults={
					'conversation': conversation, 'direction': 'outbound',
					'message_type': 'template', 'body': body,
				},
			)
	return sent


def verify_webhook_signature(request):
	app_secret = settings.WHATSAPP_APP_SECRET
	if not app_secret:
		return False
	signature = request.headers.get('X-Hub-Signature-256', '')
	if not signature.startswith('sha256='):
		return False
	expected = hmac.new(app_secret.encode(), request.body, hashlib.sha256).hexdigest()
	return hmac.compare_digest(signature[7:], expected)


def process_webhook(payload):
	for entry in payload.get('entry', []):
		for change in entry.get('changes', []):
			value = change.get('value', {})
			for message in value.get('messages', []):
				sender = normalize_phone(message.get('from', ''))
				message_id = message.get('id')
				if not sender or not message_id:
					continue
				conversation, _ = WhatsAppConversation.objects.get_or_create(phone_number=sender)
				if conversation.inquiry_id is None:
					possible_matches = [
						inquiry for inquiry in PatientInquiry.objects.only('id', 'phone_number')
						if normalize_phone(inquiry.phone_number) == sender
					]
					if len(possible_matches) == 1:
						conversation.inquiry = possible_matches[0]
						conversation.save(update_fields=['inquiry', 'updated_at'])
				try:
					timestamp = datetime.fromtimestamp(
						int(message.get('timestamp', 0)), tz=dt_timezone.utc
					)
				except (TypeError, ValueError, OverflowError):
					timestamp = timezone.now()
				body = message.get('text', {}).get('body', '')
				_, created = WhatsAppMessage.objects.get_or_create(
					message_id=message_id,
					defaults={
						'conversation': conversation,
						'direction': 'inbound',
						'message_type': message.get('type', 'unknown'),
						'body': body if isinstance(body, str) else '',
						'wa_timestamp': timestamp,
					},
				)
				if created and (
					conversation.last_inbound_at is None
					or timestamp > conversation.last_inbound_at
				):
					conversation.last_inbound_at = timestamp
					conversation.save(update_fields=['last_inbound_at', 'updated_at'])
