from io import BytesIO
import json
import os
import random
import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core import mail
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from .forms import (
	MAX_TREATMENT_IMAGE_SIZE,
	LocationForm,
	PatientInquiryForm,
	TreatmentForm,
)
from .models import (
	Location, PatientBill, PatientInquiry, Treatment, WhatsAppConversation,
	WhatsAppMessage, WhatsAppNotification,
)


@override_settings(WHATSAPP_ENABLED=False)
class PatientInquiryTests(TestCase):
	@classmethod
	def setUpTestData(cls):
		knee, _ = Treatment.objects.get_or_create(name='Knee Pain')
		neck, _ = Treatment.objects.get_or_create(name='Neck Pain')
		whitefield, _ = Location.objects.get_or_create(name='Whitefield Clinic')
		brookefield, _ = Location.objects.get_or_create(name='Brookefield Clinic')

		cls.knee = knee
		cls.neck = neck
		cls.whitefield = whitefield
		cls.brookefield = brookefield

	def test_form_has_dropdown_choices_for_treatments_and_locations(self):
		form = PatientInquiryForm()

		self.assertGreater(len(form.fields['treatment'].choices), 1)
		self.assertGreater(len(form.fields['location'].choices), 1)
		self.assertIn('Knee Pain', [str(choice[1]) for choice in form.fields['treatment'].choices])
		self.assertIn('Whitefield Clinic', [str(choice[1]) for choice in form.fields['location'].choices])

	def test_form_requires_all_fields(self):
		form = PatientInquiryForm({})

		self.assertFalse(form.is_valid())
		self.assertEqual(
			set(form.errors),
			{
				'full_name',
				'phone_number',
				'email',
				'treatment',
				'location',
			},
		)

	def test_form_rejects_invalid_phone_format(self):
		form = PatientInquiryForm({
			'treatment': self.knee.pk,
			'full_name': 'Asha Rao',
			'phone_number': 'ABC123',
			'email': 'asha@example.com',
			'location': self.whitefield.pk,
		})

		self.assertFalse(form.is_valid())
		self.assertIn('phone_number', form.errors)

	def test_form_rejects_phone_numbers_that_are_not_exactly_10_digits(self):
		for phone_number in (
			'987654321',
			'98765432101',
			'987-654-3210',
			'+919876543210',
			'９８７６５４３２１０',
		):
			with self.subTest(phone_number=phone_number):
				form = PatientInquiryForm({
					'treatment': self.knee.pk,
					'full_name': 'Asha Rao',
					'phone_number': phone_number,
					'email': 'asha@example.com',
					'location': self.whitefield.pk,
				})

				self.assertFalse(form.is_valid())
				self.assertIn('phone_number', form.errors)

	def test_appointment_phone_input_limits_entry_to_10_digits(self):
		response = self.client.get(reverse('home'))

		self.assertContains(response, 'maxlength="10"')
		self.assertContains(response, 'inputmode="numeric"')
		self.assertContains(response, 'pattern="[0-9]{10}"')

	def test_form_rejects_invalid_email(self):
		form = PatientInquiryForm({
			'treatment': self.knee.pk,
			'full_name': 'Asha Rao',
			'phone_number': '9876543210',
			'email': 'not-an-email',
			'location': self.whitefield.pk,
		})

		self.assertFalse(form.is_valid())
		self.assertIn('email', form.errors)

	def test_form_rejects_duplicate_phone_number(self):
		PatientInquiry.objects.create(
			treatment=self.knee,
			full_name='Existing User',
			phone_number='9876543210',
			email='existing@example.com',
			location=self.whitefield,
			problems='Existing issue',
		)
		form = PatientInquiryForm({
			'treatment': self.neck.pk,
			'full_name': 'Asha Rao',
			'phone_number': '9876543210',
			'email': 'asha@example.com',
			'location': self.brookefield.pk,
		})

		self.assertFalse(form.is_valid())
		self.assertIn('phone_number', form.errors)

	def test_home_duplicate_phone_shows_appointment_popup_message(self):
		PatientInquiry.objects.create(
			treatment=self.knee,
			full_name='Existing User',
			phone_number='9876543210',
			email='existing@example.com',
			location=self.whitefield,
			problems='Existing issue',
		)

		response = self.client.post(
			reverse('home'),
			{
				'next': reverse('service_page', kwargs={'service': 'knee-pain'}),
				'treatment': self.neck.pk,
				'full_name': 'Asha Rao',
				'phone_number': '9876543210',
				'email': 'asha@example.com',
				'location': self.brookefield.pk,
			},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.request['PATH_INFO'], '/services/knee-pain/')
		self.assertContains(response, 'This phone number is already booked. Please use a different number.')
		self.assertContains(response, 'appointment-message error')
		self.assertEqual(PatientInquiry.objects.filter(phone_number='9876543210').count(), 1)

	def test_service_duplicate_phone_shows_appointment_popup_message(self):
		PatientInquiry.objects.create(
			treatment=self.knee,
			full_name='Existing User',
			phone_number='9876543210',
			email='existing@example.com',
			location=self.whitefield,
			problems='Existing issue',
		)

		response = self.client.post(
			reverse('service_page', kwargs={'service': 'knee-pain'}),
			{
				'treatment': self.neck.pk,
				'full_name': 'Asha Rao',
				'phone_number': '9876543210',
				'email': 'asha@example.com',
				'location': self.brookefield.pk,
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'This phone number is already booked. Please use a different number.')
		self.assertContains(response, 'appointment-message error')
		self.assertEqual(PatientInquiry.objects.filter(phone_number='9876543210').count(), 1)

	def test_form_accepts_valid_dropdown_values_even_if_the_pair_is_not_predefined(self):
		form = PatientInquiryForm({
			'treatment': self.knee.pk,
			'full_name': 'Asha Rao',
			'phone_number': '9876543211',
			'email': 'asha@example.com',
			'location': self.brookefield.pk,
		})

		self.assertTrue(form.is_valid())
		booking = form.save()
		self.assertEqual(booking.phone_number, '9876543211')

	def test_patient_form_leaves_appointment_scheduling_to_doctor(self):
		form = PatientInquiryForm()
		self.assertNotIn('appointment_date', form.fields)
		self.assertNotIn('appointment_time', form.fields)

		response = self.client.post(reverse('home'), {
			'full_name': 'Schedule Later Patient',
			'phone_number': '9876543299',
			'email': 'schedule@example.com',
			'treatment': self.knee.pk,
			'location': self.whitefield.pk,
			'appointment_date': (timezone.localdate() + timedelta(days=4)).isoformat(),
			'appointment_time': '11:30',
		})

		self.assertRedirects(response, '/home/?success=1')
		booking = PatientInquiry.objects.get(phone_number='9876543299')
		self.assertIsNone(booking.appointment_date)
		self.assertIsNone(booking.appointment_time)
		self.assertEqual(booking.status, PatientInquiry.Status.NEW)

	def test_service_page_saves_valid_submission(self):
		response = self.client.post(
			'/services/knee-pain/',
			{
				'treatment': self.knee.pk,
				'full_name': 'Asha Rao',
				'phone_number': '9876543210',
				'email': 'asha@example.com',
				'location': self.whitefield.pk,
				'problems': 'Knee pain while walking',
			},
		)

		self.assertRedirects(response, '/services/knee-pain/?success=1')
		self.assertTrue(
			PatientInquiry.objects.filter(full_name='Asha Rao').exists()
		)

	def test_home_saves_patient_form_submission(self):
		response = self.client.post(
			'/home/',
			{
				'treatment': self.knee.pk,
				'full_name': 'Ravi Kumar',
				'phone_number': '9876543210',
				'email': 'ravi@example.com',
				'location': self.whitefield.pk,
				'problems': 'Lower back pain',
			},
		)

		self.assertRedirects(response, '/home/?success=1')
		self.assertTrue(
			PatientInquiry.objects.filter(full_name='Ravi Kumar').exists()
		)

	def test_popup_booking_returns_to_origin_and_shows_success_message(self):
		response = self.client.post(
			reverse('home'),
			{
				'next': reverse('service_page', kwargs={'service': 'knee-pain'}),
				'treatment': self.knee.pk,
				'full_name': 'Popup Patient',
				'phone_number': '9876543288',
				'email': 'popup@example.com',
				'location': self.whitefield.pk,
			},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.request['PATH_INFO'], '/services/knee-pain/')
		self.assertContains(response, 'appointment-message success')
		self.assertContains(response, 'PT-')
		self.assertNotContains(response, 'class="appointment-form--hidden"')

	def test_home_booking_sends_approved_template_with_database_values(self):
		WhatsAppConversation.objects.create(
			phone_number='919876543210', last_inbound_at=timezone.now() - timedelta(hours=1),
		)
		with override_settings(
			WHATSAPP_ENABLED=True,
			WHATSAPP_ACCESS_TOKEN='test-token',
			WHATSAPP_PHONE_NUMBER_ID='sender-id',
			WHATSAPP_DOCTOR_NUMBER='919876543210',
			WHATSAPP_DOCTOR_NAME='Dr. Sample',
			WHATSAPP_DEFAULT_COUNTRY_CODE='91',
			WHATSAPP_APPOINTMENT_TEMPLATE='appointment_notification',
			WHATSAPP_TEMPLATE_LANGUAGE='en',
			WHATSAPP_API_VERSION='v23.0',
		):
			with patch('app1.whatsapp.dotenv_values', return_value={}), patch('app1.whatsapp.urlopen') as mock_urlopen:
				mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"messages":[{"id":"wamid.out-1"}]}'
				response = self.client.post(
					reverse('home'),
					{
						'treatment': self.knee.pk,
						'full_name': 'WhatsApp Test Patient',
						'phone_number': '9876543220',
						'email': 'whatsapp@example.com',
						'location': self.whitefield.pk,
						'problems': 'Shoulder\npain\tafter exercise',
					},
				)

		self.assertEqual(response.status_code, 302)
		self.assertTrue(
			PatientInquiry.objects.filter(
				full_name='WhatsApp Test Patient'
			).exists()
		)
		request = mock_urlopen.call_args.args[0]
		payload = json.loads(request.data)
		self.assertEqual(payload['to'], '919876543210')
		self.assertEqual(payload['type'], 'template')
		self.assertEqual(payload['template']['name'], 'appointment_notification')
		self.assertEqual(payload['template']['language']['code'], 'en')
		message = payload['template']['components'][0]['parameters'][0]['text']
		self.assertIn('Appointment ID: PT-', message)
		self.assertIn('Hello Dr. Sample,', message)
		self.assertIn('WhatsApp Test Patient', message)
		self.assertIn('PT-', message)
		self.assertIn('Phone: +91 98765 43220', message)
		self.assertIn('Email: whatsapp@example.com', message)
		self.assertIn('Date & Time:', message)
		self.assertIn('Not Scheduled', message)
		self.assertIn('Concern: Knee Pain', message)
		self.assertIn('Location: Whitefield Clinic', message)
		self.assertIn('Shoulder pain after exercise', ' '.join(message.split()))
		self.assertIn('PATIENT DETAILS', message)
		self.assertIn('APPOINTMENT DETAILS', message)
		self.assertIn('ACTION REQUIRED', message)
		self.assertNotIn('\n', message)
		self.assertLessEqual(len(message), 1000)
		self.assertEqual(WhatsAppNotification.objects.get().status, 'sent')
		self.assertEqual(WhatsAppNotification.objects.get().last_reason, 'approved_template')

	def test_whatsapp_doctor_name_uses_current_dotenv_value(self):
		from .whatsapp import _doctor_name_from_env

		with patch(
			'app1.whatsapp.dotenv_values',
			return_value={'WHATSAPP_DOCTOR_NAME': 'Dr. Current Name'},
		):
			self.assertEqual(_doctor_name_from_env(), 'Dr. Current Name')

	def test_home_booking_uses_template_when_window_is_closed(self):
		with override_settings(
			WHATSAPP_ENABLED=True,
			WHATSAPP_ACCESS_TOKEN='test-token',
			WHATSAPP_PHONE_NUMBER_ID='sender-id',
			WHATSAPP_DOCTOR_NUMBER='919876543210',
			WHATSAPP_APPOINTMENT_TEMPLATE='appointment_notification',
			WHATSAPP_TEMPLATE_LANGUAGE='en',
			WHATSAPP_API_VERSION='v23.0',
		):
			with patch('app1.whatsapp.urlopen') as mock_urlopen:
				mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"messages":[{"id":"wamid.closed-window"}]}'
				response = self.client.post(
					reverse('home'),
					{
						'treatment': self.knee.pk,
						'full_name': 'Hello World Test Patient',
						'phone_number': '9876543221',
						'email': 'hello-world@example.com',
						'location': self.whitefield.pk,
					},
				)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(mock_urlopen.call_count, 1)
		payload = json.loads(mock_urlopen.call_args.args[0].data)
		self.assertEqual(payload['type'], 'template')
		notification = WhatsAppNotification.objects.get()
		self.assertEqual(notification.status, 'sent')
		self.assertEqual(notification.last_reason, 'approved_template')

	def test_booking_remains_saved_when_whatsapp_api_fails(self):
		WhatsAppConversation.objects.create(
			phone_number='919876543210', last_inbound_at=timezone.now() - timedelta(minutes=10),
		)
		with override_settings(
			WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='token',
			WHATSAPP_PHONE_NUMBER_ID='sender-id', WHATSAPP_DOCTOR_NUMBER='919876543210',
		):
			with patch('app1.whatsapp.urlopen', side_effect=OSError('network unavailable')):
				response = self.client.post(reverse('home'), {
					'treatment': self.knee.pk, 'full_name': 'Saved Patient',
					'phone_number': '9876543222', 'email': 'saved@example.com',
					'location': self.whitefield.pk,
				})
		self.assertEqual(response.status_code, 302)
		self.assertTrue(PatientInquiry.objects.filter(full_name='Saved Patient').exists())
		self.assertEqual(WhatsAppNotification.objects.get().status, 'failed')
		self.assertEqual(WhatsAppNotification.objects.get().last_reason, 'transport_error')

	def test_successful_notification_is_not_sent_again_when_retried(self):
		from .whatsapp import notify_doctor_of_booking

		booking = PatientInquiry.objects.create(
			treatment=self.knee, full_name='Retry Patient', phone_number='9876543223',
			email='retry@example.com', location=self.whitefield,
		)
		WhatsAppConversation.objects.create(
			phone_number='919876543210', last_inbound_at=timezone.now() - timedelta(minutes=1),
		)
		with override_settings(
			WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='token',
			WHATSAPP_PHONE_NUMBER_ID='sender-id', WHATSAPP_DOCTOR_NUMBER='919876543210',
		):
			with patch('app1.whatsapp.urlopen') as mock_urlopen:
				mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"messages":[{"id":"wamid.retry"}]}'
				self.assertTrue(notify_doctor_of_booking(booking))
				self.assertTrue(notify_doctor_of_booking(booking))
		self.assertEqual(mock_urlopen.call_count, 1)
		self.assertEqual(WhatsAppNotification.objects.get().attempts, 1)

	def test_retry_command_retries_401_after_credentials_are_replaced(self):
		booking = PatientInquiry.objects.create(
			full_name='Auth Retry Patient', phone_number='9876543226',
			email='auth-retry@example.com',
		)
		WhatsAppNotification.objects.create(
			inquiry=booking,
			status=WhatsAppNotification.Status.FAILED,
			attempts=1,
			last_reason='http_401',
		)
		with override_settings(
			WHATSAPP_ENABLED=True,
			WHATSAPP_ACCESS_TOKEN='replacement-test-token',
			WHATSAPP_PHONE_NUMBER_ID='sender-id',
			WHATSAPP_DOCTOR_NUMBER='919876543210',
			WHATSAPP_APPOINTMENT_TEMPLATE='appointment_notification',
			WHATSAPP_TEMPLATE_LANGUAGE='en',
		):
			with patch('app1.whatsapp.urlopen') as mock_urlopen:
				mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"messages":[{"id":"wamid.auth-retry"}]}'
				call_command('retry_whatsapp_notifications', verbosity=0)
		self.assertEqual(WhatsAppNotification.objects.get().status, 'sent')
		self.assertEqual(WhatsAppNotification.objects.get().attempts, 2)

	def test_invalid_doctor_number_is_recorded_without_api_call(self):
		from .whatsapp import notify_doctor_of_booking

		booking = PatientInquiry.objects.create(
			full_name='Invalid Recipient', phone_number='9876543224', email='invalid@example.com',
		)
		WhatsAppConversation.objects.create(phone_number='123', last_inbound_at=timezone.now())
		with override_settings(
			WHATSAPP_ENABLED=True, WHATSAPP_ACCESS_TOKEN='token',
			WHATSAPP_PHONE_NUMBER_ID='sender-id', WHATSAPP_DOCTOR_NUMBER='123',
		):
			with patch('app1.whatsapp.urlopen') as mock_urlopen:
				self.assertFalse(notify_doctor_of_booking(booking))
		mock_urlopen.assert_not_called()
		self.assertEqual(WhatsAppNotification.objects.get().last_reason, 'invalid_recipient_number')

	@override_settings(
		WHATSAPP_WEBHOOK_VERIFY_TOKEN='verify-me', WHATSAPP_APP_SECRET='app-secret',
	)
	def test_whatsapp_webhook_verifies_and_stores_inbound_message_once(self):
		verify = self.client.get(reverse('whatsapp_webhook'), {
			'hub.mode': 'subscribe', 'hub.verify_token': 'verify-me', 'hub.challenge': '12345',
		})
		self.assertEqual(verify.status_code, 200)
		self.assertEqual(verify.content, b'12345')
		incoming_timestamp = int(timezone.now().timestamp())
		payload = json.dumps({'entry': [{'changes': [{'value': {'messages': [{
			'from': '919876543210', 'id': 'wamid.in-1', 'timestamp': str(incoming_timestamp),
			'type': 'text', 'text': {'body': 'Can you confirm my appointment?'}
		}]}}]}]}).encode()
		signature = hmac.new(b'app-secret', payload, hashlib.sha256).hexdigest()
		for _ in range(2):
			response = self.client.post(
				reverse('whatsapp_webhook'), data=payload, content_type='application/json',
				HTTP_X_HUB_SIGNATURE_256=f'sha256={signature}',
			)
			self.assertEqual(response.status_code, 200)
		self.assertEqual(WhatsAppMessage.objects.count(), 1)
		self.assertEqual(int(WhatsAppConversation.objects.get().last_inbound_at.timestamp()), incoming_timestamp)

	def test_unknown_whatsapp_sender_is_visible_only_to_doctor_users(self):
		conversation = WhatsAppConversation.objects.create(phone_number='919800000000')
		WhatsAppMessage.objects.create(
			conversation=conversation, message_id='wamid.unknown', direction='inbound',
			message_type='text', body='Who is this?',
		)
		self.assertEqual(self.client.get(reverse('doctor_whatsapp_inbox')).status_code, 302)
		doctor = get_user_model().objects.create_user(username='inbox-doctor', password='test-pass', is_staff=True)
		doctor.groups.add(Group.objects.get_or_create(name='Doctors')[0])
		self.client.force_login(doctor)
		response = self.client.get(reverse('doctor_whatsapp_inbox'))
		self.assertContains(response, '919800000000')
		self.assertContains(response, 'Who is this?')



class HomeTreatmentCardTests(TestCase):
	def test_logged_in_doctor_sees_public_navigation_on_home(self):
		doctor_group, _ = Group.objects.get_or_create(name='Doctors')
		doctor = get_user_model().objects.create_user(
			username='doctor-home',
			password='test-password-123',
			is_staff=True,
		)
		doctor.groups.add(doctor_group)
		self.client.force_login(doctor)

		response = self.client.get(reverse('home'))

		self.assertFalse(response.context['is_doctor_portal'])
		self.assertContains(response, 'Book Appointment')
		self.assertNotContains(response, 'PATIENT BOOKINGS')

	def test_home_shows_treatments_from_database_instead_of_static_cards(self):
		treatment = Treatment.objects.create(name='Manual Therapy')
		Treatment.objects.create(name='Sports Rehabilitation')

		response = self.client.get(reverse('home'))

		self.assertContains(response, 'Manual Therapy')
		self.assertContains(response, 'Sports Rehabilitation')
		detail_url = reverse(
			'treatment_detail',
			kwargs={'treatment_slug': treatment.url_slug, 'treatment_id': treatment.pk},
		)
		self.assertContains(response, detail_url)
		self.assertNotContains(response, 'knee-ankle.jpg')
		self.assertNotContains(response, 'view-more-conditions')
		self.assertEqual(response.context['treatments'].count(), 2)

	def test_services_navigation_lists_treatments_and_links_to_detail_page(self):
		treatment = Treatment.objects.create(name='Manual Therapy')

		response = self.client.get(reverse('home'))

		self.assertContains(response, 'Manual Therapy')
		self.assertContains(response, reverse(
			'treatment_detail',
			kwargs={'treatment_slug': treatment.url_slug, 'treatment_id': treatment.pk},
		))

	def test_treatment_detail_shows_selected_treatment_and_prefills_booking_form(self):
		treatment = Treatment.objects.create(
			name='Manual Therapy',
			description='A sample patient-facing treatment description.',
		)

		response = self.client.get(reverse(
			'treatment_detail',
			kwargs={'treatment_slug': treatment.url_slug, 'treatment_id': treatment.pk},
		))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Manual Therapy')
		self.assertContains(response, 'A sample patient-facing treatment description.')
		self.assertContains(response, 'class="treatment-detail-main"')
		self.assertContains(response, 'class="treatment-detail-booking-card"')
		self.assertContains(response, 'Request an appointment')
		self.assertEqual(response.context['patient_form']['treatment'].value(), treatment.pk)

	def test_treatment_detail_renders_faq_blocks_in_question_answer_format(self):
		treatment = Treatment.objects.create(
			name='Manual Therapy',
			description=(
				'This treatment helps improve movement and reduce discomfort.\n\n'
				'Frequently Asked Questions\n'
				'Q: Will this help with pain?\n'
				'A: It can reduce discomfort and improve movement when guided by a physiotherapist.\n\n'
				'Q: How many sessions will I need?\n'
				'A: The number of sessions depends on your goals and progress.'
			),
		)

		response = self.client.get(reverse(
			'treatment_detail',
			kwargs={'treatment_slug': treatment.url_slug, 'treatment_id': treatment.pk},
		))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Frequently Asked Questions')
		self.assertContains(response, 'class="treatment-faq-question"')
		self.assertContains(response, 'class="treatment-faq-answer"')

	def test_treatment_detail_parses_realistic_ai_faq_without_q_a_markers(self):
		treatment = Treatment.objects.create(
			name='Back & Neck',
			description=(
				'Physiotherapy for the back and neck focuses on reducing discomfort.\n\n'
				'Frequently Asked Questions\n\n'
				'Will the treatment hurt?\n'
				'You may feel mild stretching or muscle fatigue during the session, but this is usually manageable.\n\n'
				'How long will I need treatment?\n'
				'The number of sessions depends on your symptoms, goals, and progress with the plan.'
			),
		)

		response = self.client.get(reverse(
			'treatment_detail',
			kwargs={'treatment_slug': treatment.url_slug, 'treatment_id': treatment.pk},
		))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Will the treatment hurt?')
		self.assertContains(response, 'class="treatment-faq-question"')
		self.assertContains(response, 'class="treatment-faq-answer"')

	def test_treatment_detail_redirects_to_name_based_canonical_url(self):
		treatment = Treatment.objects.create(name='Back & Neck')
		response = self.client.get(
			reverse(
				'treatment_detail',
				kwargs={'treatment_slug': 'old-name', 'treatment_id': treatment.pk},
			)
		)

		self.assertRedirects(
			response,
			reverse(
				'treatment_detail',
				kwargs={'treatment_slug': treatment.url_slug, 'treatment_id': treatment.pk},
			),
			status_code=301,
		)

	def test_previous_id_only_treatment_url_redirects_to_name_based_url(self):
		treatment = Treatment.objects.create(name='Back & Neck')
		response = self.client.get(
			reverse('legacy_treatment_detail', kwargs={'treatment_id': treatment.pk})
		)

		self.assertRedirects(
			response,
			reverse(
				'treatment_detail',
				kwargs={'treatment_slug': treatment.url_slug, 'treatment_id': treatment.pk},
			),
			status_code=301,
		)


class AboutTreatmentCardTests(TestCase):
	def test_about_lists_database_treatments_with_canonical_links(self):
		treatment = Treatment.objects.create(name='Post Operative Therapy')
		response = self.client.get(reverse('about'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Post Operative Therapy')
		self.assertContains(response, reverse(
			'treatment_detail',
			kwargs={'treatment_slug': treatment.url_slug, 'treatment_id': treatment.pk},
		))
		self.assertNotContains(response, 'post-operative.jpg')
		self.assertEqual(response.context['treatments'].count(), 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DoctorCatalogTests(TestCase):
	def setUp(self):
		self.doctor_group, _ = Group.objects.get_or_create(name='Doctors')
		self.doctor = get_user_model().objects.create_user(
			username='doctor',
			email='doctor@example.com',
			password='test-password-123',
			is_staff=True,
		)
		self.doctor.groups.add(self.doctor_group)

	def test_catalog_requires_doctor_login(self):
		response = self.client.get(reverse('doctor_catalog'))
		self.assertRedirects(response, f"{reverse('doctor_login')}?next={reverse('doctor_catalog')}")

	def test_doctor_catalog_renders_separate_styled_forms(self):
		self.client.force_login(self.doctor)
		response = self.client.get(reverse('doctor_catalog'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Add treatment')
		self.assertContains(response, 'Add location')
		self.assertContains(response, 'doctor.css')
		self.assertContains(response, 'Current treatments')
		self.assertContains(response, 'Current locations')
		self.assertContains(response, 'Maximum file size: 5 MB.')
		self.assertContains(response, 'Generate draft')
		self.assertContains(response, 'doctor.js')
		self.assertContains(response, 'PATIENT BOOKINGS')
		self.assertContains(response, 'SIGN OUT')
		self.assertNotContains(response, 'Book Appointment')

	def test_doctor_bookings_page_shows_and_searches_patient_bookings(self):
		treatment = Treatment.objects.create(name='Sports Physiotherapy')
		location = Location.objects.create(name='Whitefield Clinic')
		PatientInquiry.objects.create(
			treatment=treatment,
			location=location,
			full_name='Patient Example',
			phone_number='9876543210',
			email='patient@example.com',
			problems='Shoulder pain after exercise',
		)
		PatientInquiry.objects.create(
			full_name='Future Patient',
			phone_number='9876543214',
			email='future@example.com',
			appointment_date=timezone.localdate() + timedelta(days=2),
		)
		self.client.force_login(self.doctor)

		default_response = self.client.get(reverse('doctor_bookings'))
		self.assertContains(default_response, 'Patient Example')
		self.assertContains(default_response, 'Future Patient')
		self.assertEqual(default_response.context['period'], 'all')
		self.assertEqual(default_response.context['booking_count'], 2)
		self.assertNotContains(default_response, 'All statuses')

		response = self.client.get(reverse('doctor_bookings'), {'period': 'unscheduled'})

		self.assertContains(response, 'Patient Example')
		self.assertContains(response, 'Future Patient')
		self.assertContains(response, '9876543210')
		self.assertContains(response, 'patient@example.com')
		self.assertContains(response, 'Sports Physiotherapy')
		self.assertContains(response, 'Shoulder pain after exercise')
		self.assertEqual(response.context['booking_count'], 2)

		search_response = self.client.get(reverse('doctor_bookings'), {'period': 'unscheduled', 'q': 'Whitefield'})
		self.assertContains(search_response, 'Patient Example')
		self.assertEqual(search_response.context['booking_count'], 1)

		no_match_response = self.client.get(reverse('doctor_bookings'), {'period': 'unscheduled', 'q': 'No such patient'})
		self.assertContains(no_match_response, 'No bookings in this view.')
		self.assertNotContains(no_match_response, 'patient@example.com')

	def test_doctor_bookings_support_day_week_and_unscheduled_views(self):
		today = timezone.localdate()
		week_start = today - timedelta(days=today.weekday())
		today_booking = PatientInquiry.objects.create(
			full_name='Today Patient', phone_number='9876543210', email='today@example.com',
			appointment_date=today, appointment_time='10:30',
		)
		PatientInquiry.objects.create(
			full_name='Earlier This Week', phone_number='9876543211', email='week@example.com',
			appointment_date=week_start,
		)
		PatientInquiry.objects.create(
			full_name='Unscheduled Patient', phone_number='9876543212', email='later@example.com',
		)
		self.client.force_login(self.doctor)

		day_response = self.client.get(reverse('doctor_bookings'), {'period': 'day', 'date': today.isoformat()})
		self.assertContains(day_response, 'Today Patient')
		self.assertContains(day_response, '10:30')
		self.assertContains(day_response, 'All statuses')
		self.assertContains(day_response, 'Unscheduled')
		self.assertContains(day_response, 'Scheduled')
		self.assertContains(day_response, 'Completed')
		self.assertContains(day_response, 'Cancelled')
		self.assertContains(day_response, 'doctor-status-summary')
		self.assertNotContains(day_response, 'doctor-booking-status-tabs')
		self.assertEqual(day_response.context['booking_count'], 1)

		week_response = self.client.get(reverse('doctor_bookings'), {'period': 'week', 'date': today.isoformat()})
		self.assertContains(week_response, 'Today Patient')
		self.assertContains(week_response, 'Earlier This Week')
		self.assertEqual(week_response.context['booking_count'], 2)

		unscheduled_response = self.client.get(reverse('doctor_bookings'), {'period': 'unscheduled'})
		self.assertContains(unscheduled_response, 'Unscheduled Patient')
		self.assertContains(unscheduled_response, 'Today Patient')
		self.assertContains(unscheduled_response, 'Earlier This Week')
		self.assertEqual(unscheduled_response.context['booking_count'], 3)
		self.assertEqual(today_booking.status, PatientInquiry.Status.NEW)

	def test_month_and_day_status_filters(self):
		today = timezone.localdate()
		patients_by_status = {
			PatientInquiry.Status.NEW: 'New Day Patient',
			PatientInquiry.Status.SCHEDULED: 'Scheduled Day Patient',
			PatientInquiry.Status.COMPLETED: 'Completed Day Patient',
			PatientInquiry.Status.CANCELLED: 'Cancelled Day Patient',
		}
		for index, (status, name) in enumerate(patients_by_status.items()):
			PatientInquiry.objects.create(
				full_name=name,
				phone_number=f'98765432{20 + index:02d}',
				email=f'day{index}@example.com',
				appointment_date=today,
				status=status,
			)
		previous_month = today.replace(day=1) - timedelta(days=1)
		PatientInquiry.objects.create(
			full_name='Previous Month Patient',
			phone_number='9876543290',
			email='previous-month@example.com',
			appointment_date=previous_month,
			status=PatientInquiry.Status.SCHEDULED,
		)
		self.client.force_login(self.doctor)

		month_response = self.client.get(reverse('doctor_bookings'), {
			'period': 'month',
			'date': today.isoformat(),
		})
		self.assertEqual(month_response.context['period_label'], today.strftime('%B %Y'))
		self.assertEqual(month_response.context['booking_count'], 4)
		self.assertContains(month_response, 'Month')
		self.assertNotContains(month_response, 'Previous Month Patient')

		for status, expected_name in [
			('unscheduled', 'New Day Patient'),
			(PatientInquiry.Status.SCHEDULED, 'Scheduled Day Patient'),
			(PatientInquiry.Status.COMPLETED, 'Completed Day Patient'),
			(PatientInquiry.Status.CANCELLED, 'Cancelled Day Patient'),
		]:
			response = self.client.get(reverse('doctor_bookings'), {
				'period': 'day',
				'date': today.isoformat(),
				'status': status,
			})
			self.assertContains(response, expected_name)
			self.assertEqual(response.context['booking_count'], 1)
			self.assertEqual(response.context['status_counts']['all'], 4)

	def test_doctor_can_see_whatsapp_notification_status_on_booking_pages(self):
		booking = PatientInquiry.objects.create(
			full_name='Visible Alert Patient', phone_number='9876543299',
			email='visible-alert@example.com',
		)
		WhatsAppNotification.objects.create(
			inquiry=booking,
			status=WhatsAppNotification.Status.SENT,
			last_reason='approved_template',
		)
		self.client.force_login(self.doctor)
		bookings_response = self.client.get(reverse('doctor_bookings'))
		self.assertContains(bookings_response, 'WhatsApp alert')
		self.assertContains(bookings_response, 'Meta template')
		detail_response = self.client.get(reverse('doctor_booking_detail', args=[booking.pk]))
		self.assertContains(detail_response, 'Doctor WhatsApp alert')
		self.assertContains(detail_response, 'Meta template')

	@override_settings(
		WHATSAPP_ENABLED=True,
		WHATSAPP_ACCESS_TOKEN='test-token',
		WHATSAPP_PHONE_NUMBER_ID='sender-id',
		WHATSAPP_DOCTOR_NUMBER='919876543210',
		WHATSAPP_APPOINTMENT_TEMPLATE='appointment_notification',
		WHATSAPP_PATIENT_APPOINTMENT_TEMPLATE='patient_appointment_confirmation',
		WHATSAPP_PATIENT_BILL_TEMPLATE='patient_bill_notification',
		WHATSAPP_TEMPLATE_LANGUAGE='en',
		WHATSAPP_API_VERSION='v23.0',
	)
	@patch('app1.views.urlopen')
	def test_doctor_can_schedule_booking_and_create_whatsapp_bill(self, mock_urlopen):
		booking = PatientInquiry.objects.create(
			full_name='Bill Patient', phone_number='9876543213', email='bill@example.com',
			problems='Knee pain', whatsapp_consent=True,
		)
		self.client.force_login(self.doctor)
		response = self.client.post(reverse('doctor_booking_detail', args=[booking.pk]), {
			'action': 'schedule',
			'appointment_date': timezone.localdate().isoformat(),
			'appointment_time': '14:15',
			'status': PatientInquiry.Status.SCHEDULED,
		})
		self.assertRedirects(response, reverse('doctor_booking_detail', args=[booking.pk]))
		booking.refresh_from_db()
		self.assertEqual(booking.status, PatientInquiry.Status.SCHEDULED)
		self.assertEqual(str(booking.appointment_time), '14:15:00')
		schedule_payload = json.loads(mock_urlopen.call_args_list[0].args[0].data)
		self.assertEqual(schedule_payload['to'], '919876543213')
		self.assertEqual(
			schedule_payload['template']['name'],
			'patient_appointment_confirmation',
		)
		schedule_message = schedule_payload['template']['components'][0]['parameters'][0]['text']
		self.assertIn('Bill Patient', schedule_message)
		self.assertIn(timezone.localdate().strftime('%d %b %Y'), schedule_message)
		self.assertIn('02:15 PM', schedule_message)

		response = self.client.post(reverse('doctor_booking_detail', args=[booking.pk]), {
			'action': 'create_bill',
			'service_description': 'Initial physiotherapy consultation',
			'amount': '850.00',
			'notes': 'One session',
		})
		bill = booking.bills.get()
		self.assertRedirects(response, reverse('doctor_bill_detail', args=[bill.pk]))
		self.assertEqual(bill.amount, Decimal('850.00'))
		bill_payload = json.loads(mock_urlopen.call_args_list[1].args[0].data)
		self.assertEqual(bill_payload['to'], '919876543213')
		self.assertEqual(
			bill_payload['template']['name'],
			'patient_bill_notification',
		)
		bill_message = bill_payload['template']['components'][0]['parameters'][0]['text']
		self.assertIn(bill.bill_number, bill_message)
		self.assertIn('INR 850.00', bill_message)

		invoice = self.client.get(reverse('doctor_bill_detail', args=[bill.pk]))
		self.assertContains(invoice, bill.bill_number)
		self.assertContains(invoice, 'INR 850.00')
		self.assertContains(invoice, 'wa.me/919876543213')
		self.assertContains(invoice, 'Print / Save PDF')

		response = self.client.post(reverse('doctor_bill_detail', args=[bill.pk]), {'action': 'mark_paid'})
		self.assertRedirects(response, reverse('doctor_bill_detail', args=[bill.pk]))
		bill.refresh_from_db()
		self.assertEqual(bill.status, PatientBill.Status.PAID)

	@override_settings(
		WHATSAPP_ENABLED=True,
		WHATSAPP_ACCESS_TOKEN='test-token',
		WHATSAPP_PHONE_NUMBER_ID='sender-id',
		WHATSAPP_DOCTOR_NUMBER='919876543210',
		WHATSAPP_APPOINTMENT_TEMPLATE='appointment_notification',
		WHATSAPP_PATIENT_APPOINTMENT_TEMPLATE='patient_appointment_confirmation',
		WHATSAPP_PATIENT_BILL_TEMPLATE='patient_bill_notification',
		WHATSAPP_TEMPLATE_LANGUAGE='en',
		WHATSAPP_API_VERSION='v23.0',
	)
	@patch('app1.views.urlopen')
	def test_patient_notifications_are_skipped_without_whatsapp_consent(self, mock_urlopen):
		booking = PatientInquiry.objects.create(
			full_name='No Consent Patient',
			phone_number='9876543214',
			email='no-consent@example.com',
		)
		self.client.force_login(self.doctor)
		self.client.post(reverse('doctor_booking_detail', args=[booking.pk]), {
			'action': 'schedule',
			'appointment_date': timezone.localdate().isoformat(),
			'appointment_time': '14:15',
			'status': PatientInquiry.Status.SCHEDULED,
		})
		self.client.post(reverse('doctor_booking_detail', args=[booking.pk]), {
			'action': 'create_bill',
			'service_description': 'Consultation',
			'amount': '850.00',
		})
		mock_urlopen.assert_not_called()

	def test_doctor_logout_returns_to_public_site_navigation(self):
		self.client.force_login(self.doctor)

		response = self.client.post(reverse('doctor_logout'), follow=True)

		self.assertRedirects(response, reverse('home'))
		self.assertFalse(response.wsgi_request.user.is_authenticated)
		self.assertContains(response, 'Book Appointment')
		self.assertContains(response, 'Staff Login')
		self.assertNotContains(response, 'PATIENT BOOKINGS')

	def test_staff_without_doctor_group_is_denied(self):
		user = get_user_model().objects.create_user(
			username='staff',
			password='test-password-123',
			is_staff=True,
		)
		response = self.client.post(reverse('doctor_login'), {
			'username': 'staff',
			'password': 'test-password-123',
		})
		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.wsgi_request.user.is_authenticated)

		self.client.force_login(user)
		self.assertEqual(self.client.get(reverse('doctor_catalog')).status_code, 403)

	def test_doctor_can_sign_in(self):
		response = self.client.post(reverse('doctor_login'), {
			'username': 'doctor',
			'password': 'test-password-123',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Enter the six-digit code sent to your email')
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['doctor@example.com'])
		self.assertFalse(response.wsgi_request.user.is_authenticated)

		self.assertIn('Physio Whitefield', mail.outbox[0].subject)
		self.assertIn('one-time code', mail.outbox[0].body)
		self.assertEqual(mail.outbox[0].alternatives[0][1], 'text/html')
		otp = mail.outbox[0].body.split('Your one-time code: ', 1)[1].splitlines()[0]
		response = self.client.post(reverse('doctor_login'), {
			'stage': 'otp',
			'otp': otp,
		})

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response['Location'], reverse('doctor_catalog'))
		catalog_response = self.client.get(response['Location'])
		self.assertContains(catalog_response, 'Doctor login successful.')

	def test_wrong_password_does_not_send_doctor_otp(self):
		response = self.client.post(reverse('doctor_login'), {
			'username': 'doctor',
			'password': 'wrong-password',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Username or password is incorrect')
		self.assertEqual(len(mail.outbox), 0)
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	def test_incorrect_doctor_otp_does_not_log_in(self):
		self.client.post(reverse('doctor_login'), {
			'username': 'doctor',
			'password': 'test-password-123',
		})
		response = self.client.post(reverse('doctor_login'), {
			'stage': 'otp',
			'otp': '000000',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'email sign-in code is incorrect')
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	def test_doctor_login_returns_to_requested_catalog_url(self):
		location = Location.objects.create(name='Requested catalog location')
		catalog_url = f"{reverse('doctor_catalog')}?edit_location={location.pk}"
		login_response = self.client.get(catalog_url)

		self.assertRedirects(
			login_response,
			f"{reverse('doctor_login')}?next={catalog_url.replace('/', '%2F').replace('?', '%3F').replace('=', '%3D')}",
		)
		response = self.client.post(login_response['Location'], {
			'username': 'doctor',
			'password': 'test-password-123',
		})
		otp = mail.outbox[-1].body.split('Your one-time code: ', 1)[1].splitlines()[0]
		response = self.client.post(login_response['Location'], {
			'stage': 'otp',
			'otp': otp,
			'next': catalog_url,
		})

		self.assertRedirects(response, catalog_url)
		catalog_response = self.client.get(response['Location'])
		self.assertContains(catalog_response, 'Update location')

	def test_description_generation_requires_doctor_login(self):
		response = self.client.post(
			reverse('doctor_generate_treatment_description'),
			{'name': 'Back Pain'},
		)
		self.assertRedirects(
			response,
			f"{reverse('doctor_login')}?next={reverse('doctor_generate_treatment_description')}",
		)

	def test_description_generation_reports_missing_server_key(self):
		self.client.force_login(self.doctor)
		with patch.dict(os.environ, {'GEMINI_API_KEY': ''}):
			response = self.client.post(
				reverse('doctor_generate_treatment_description'),
				{'name': 'Back Pain'},
			)

		self.assertEqual(response.status_code, 503)
		self.assertContains(response, 'AI descriptions are not configured', status_code=503)

	def test_description_generation_returns_reviewable_draft(self):
		self.client.force_login(self.doctor)
		provider_result = {
			'candidates': [{
				'content': {
					'parts': [{'text': 'A patient-facing draft description.'}],
				},
			}],
		}
		mock_response = MagicMock()
		mock_response.__enter__.return_value.read.return_value = json.dumps(provider_result).encode('utf-8')

		with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-test-key'}):
			with patch('app1.views.urlopen', return_value=mock_response) as mock_urlopen:
				response = self.client.post(
					reverse('doctor_generate_treatment_description'),
					{'name': 'Back Pain'},
				)

		self.assertEqual(response.status_code, 200)
		self.assertJSONEqual(response.content, {
			'description': 'A patient-facing draft description.',
		})
		self.assertEqual(mock_urlopen.call_args.args[0].get_method(), 'POST')

	def test_description_generation_uses_uploaded_reference_image(self):
		self.client.force_login(self.doctor)
		image_buffer = BytesIO()
		Image.new('RGB', (24, 24), color='green').save(image_buffer, format='PNG')
		image = SimpleUploadedFile(
			'reference.png',
			image_buffer.getvalue(),
			content_type='image/png',
		)
		mock_response = MagicMock()
		mock_response.__enter__.return_value.read.return_value = json.dumps({
			'candidates': [{'content': {'parts': [{'text': 'Image-based draft.'}]}}],
		}).encode('utf-8')

		with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-test-key'}):
			with patch('app1.views.urlopen', return_value=mock_response) as mock_urlopen:
				response = self.client.post(
					reverse('doctor_generate_treatment_description'),
					{'name': 'Manual Therapy', 'image': image},
				)

		self.assertEqual(response.status_code, 200)
		request_payload = json.loads(mock_urlopen.call_args.args[0].data.decode('utf-8'))
		parts = request_payload['contents'][0]['parts']
		self.assertIn('Manual Therapy', parts[0]['text'])
		self.assertEqual(parts[1]['inline_data']['mime_type'], 'image/png')

	def test_description_generation_uses_saved_image_when_editing(self):
		self.client.force_login(self.doctor)
		image_buffer = BytesIO()
		Image.new('RGB', (24, 24), color='green').save(image_buffer, format='PNG')
		treatment = Treatment.objects.create(
			name='Manual Therapy',
			image=SimpleUploadedFile(
				'reference.png',
				image_buffer.getvalue(),
				content_type='image/png',
			),
		)
		mock_response = MagicMock()
		mock_response.__enter__.return_value.read.return_value = json.dumps({
			'candidates': [{'content': {'parts': [{'text': 'Saved-image draft.'}]}}],
		}).encode('utf-8')

		with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-test-key'}):
			with patch('app1.views.urlopen', return_value=mock_response) as mock_urlopen:
				response = self.client.post(
					reverse('doctor_generate_treatment_description'),
					{'name': treatment.name, 'treatment_id': treatment.pk},
				)

		self.assertEqual(response.status_code, 200)
		request_payload = json.loads(mock_urlopen.call_args.args[0].data.decode('utf-8'))
		parts = request_payload['contents'][0]['parts']
		self.assertIn('Manual Therapy', parts[0]['text'])
		self.assertEqual(parts[1]['inline_data']['mime_type'], 'image/png')

	def test_doctor_can_add_treatment_and_image_separately(self):
		image_buffer = BytesIO()
		Image.new('RGB', (100, 100), color='blue').save(image_buffer, format='PNG')
		image_buffer.seek(0)
		image = SimpleUploadedFile(
			'name.png',
			image_buffer.read(),
			content_type='image/png',
		)
		self.client.force_login(self.doctor)
		response = self.client.post(
			reverse('doctor_catalog'),
			{
				'section': 'treatment',
				'name': 'Manual Therapy',
				'description': 'A treatment description for patients.',
				'image': image,
			},
			follow=True,
		)

		self.assertRedirects(response, reverse('doctor_catalog'))
		self.assertContains(response, 'New treatment added successfully: Manual Therapy and its image.')
		self.assertContains(response, 'doctor-feedback')
		self.assertNotContains(response, 'appointment-message')
		treatment = Treatment.objects.get(name='Manual Therapy')
		self.assertTrue(treatment.image)
		self.assertEqual(treatment.description, 'A treatment description for patients.')

	def test_doctor_can_add_details_to_existing_treatment_without_an_image(self):
		treatment = Treatment.objects.create(name='Back Pain')
		self.client.force_login(self.doctor)

		edit_page = self.client.get(reverse('doctor_catalog'), {'edit_treatment': treatment.pk})
		self.assertContains(edit_page, 'Edit treatment information')

		response = self.client.post(
			reverse('doctor_catalog'),
			{
				'section': 'edit_treatment',
				'treatment_id': treatment.pk,
				'name': 'Back Pain',
				'description': 'Individual care for back pain and movement limitations.',
			},
			follow=True,
		)

		self.assertRedirects(response, reverse('doctor_catalog'))
		self.assertContains(response, 'Treatment information updated: Back Pain.')
		treatment.refresh_from_db()
		self.assertEqual(
			treatment.description,
			'Individual care for back pain and movement limitations.',
		)

	def test_treatment_form_requires_both_name_and_image(self):
		form = TreatmentForm({})

		self.assertFalse(form.is_valid())
		self.assertIn('name', form.errors)
		self.assertIn('description', form.errors)
		self.assertIn('image', form.errors)

	def test_treatment_form_rejects_duplicate_name_case_insensitively(self):
		Treatment.objects.create(name='Manual Therapy')
		image_buffer = BytesIO()
		Image.new('RGB', (100, 100), color='blue').save(image_buffer, format='PNG')
		image = SimpleUploadedFile(
			'name.png',
			image_buffer.getvalue(),
			content_type='image/png',
		)
		form = TreatmentForm(
			{'name': ' manual therapy ', 'description': 'Treatment description.'},
			{'image': image},
		)

		self.assertFalse(form.is_valid())
		self.assertIn('already exists', str(form.errors['name']))

	def test_doctor_sees_duplicate_treatment_error_without_saving_another_record(self):
		Treatment.objects.create(name='Manual Therapy')
		image_buffer = BytesIO()
		Image.new('RGB', (100, 100), color='blue').save(image_buffer, format='PNG')
		image = SimpleUploadedFile(
			'name.png',
			image_buffer.getvalue(),
			content_type='image/png',
		)
		self.client.force_login(self.doctor)
		response = self.client.post(
			reverse('doctor_catalog'),
			{
				'section': 'treatment',
				'name': 'manual therapy',
				'description': 'Treatment description.',
				'image': image,
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'A treatment with this name already exists.')
		self.assertNotContains(response, 'New treatment added successfully')
		self.assertEqual(Treatment.objects.filter(name__iexact='Manual Therapy').count(), 1)


	def test_treatment_form_rejects_images_over_5_mb(self):
		image_bytes = random.Random(7).randbytes(1600 * 1600 * 3)
		image_buffer = BytesIO()
		Image.frombytes('RGB', (1600, 1600), image_bytes).save(image_buffer, format='PNG')
		upload = SimpleUploadedFile(
			'large.png',
			image_buffer.getvalue(),
			content_type='image/png',
		)
		self.assertGreater(upload.size, MAX_TREATMENT_IMAGE_SIZE)
		form = TreatmentForm(
			{'name': 'Large Image Therapy', 'description': 'Treatment description.'},
			{'image': upload},
		)

		self.assertFalse(form.is_valid())
		self.assertIn('5 MB or less', str(form.errors['image']))

	def test_doctor_can_add_location_separately(self):
		self.client.force_login(self.doctor)
		response = self.client.post(
			reverse('doctor_catalog'),
			{'section': 'location', 'name': 'Whitefield Clinic'},
			follow=True,
		)

		self.assertRedirects(response, reverse('doctor_catalog'))
		self.assertContains(response, 'New location added successfully: Whitefield Clinic.')
		self.assertContains(response, 'doctor-feedback')
		self.assertNotContains(response, 'appointment-message')
		self.assertTrue(Location.objects.filter(name='Whitefield Clinic').exists())

	def test_doctor_can_update_location_and_keep_existing_inquiry_linked(self):
		location = Location.objects.create(name='Whitefield Clinic')
		inquiry = PatientInquiry.objects.create(
			location=location,
			full_name='Patient Three',
			phone_number='9876543212',
			email='patient@example.com',
		)
		self.client.force_login(self.doctor)

		edit_page = self.client.get(reverse('doctor_catalog'), {'edit_location': location.pk})
		self.assertContains(edit_page, 'Update location')

		response = self.client.post(
			reverse('doctor_catalog'),
			{
				'section': 'edit_location',
				'location_id': location.pk,
				'name': 'Whitefield Physiotherapy Clinic',
			},
			follow=True,
		)

		self.assertRedirects(response, reverse('doctor_catalog'))
		self.assertContains(response, 'Location updated successfully: Whitefield Physiotherapy Clinic.')
		inquiry.refresh_from_db()
		self.assertEqual(inquiry.location_id, location.pk)
		self.assertEqual(inquiry.location.name, 'Whitefield Physiotherapy Clinic')

	def test_doctor_can_delete_treatment_and_keep_existing_inquiries(self):
		image_buffer = BytesIO()
		Image.new('RGB', (100, 100), color='blue').save(image_buffer, format='PNG')
		treatment = Treatment.objects.create(
			name='Manual Therapy',
			image=SimpleUploadedFile(
				'manual.png', image_buffer.getvalue(), content_type='image/png'
			),
		)
		image_path = treatment.image.path
		inquiry = PatientInquiry.objects.create(
			treatment=treatment,
			location=None,
			full_name='Patient One',
			phone_number='9876543210',
			email='patient@example.com',
		)
		self.client.force_login(self.doctor)

		response = self.client.post(
			reverse('doctor_catalog'),
			{'section': 'delete_treatment', 'treatment_id': treatment.pk},
			follow=True,
		)

		self.assertRedirects(response, reverse('doctor_catalog'))
		self.assertContains(response, 'Treatment removed successfully: Manual Therapy.')
		self.assertFalse(Treatment.objects.filter(pk=treatment.pk).exists())
		inquiry.refresh_from_db()
		self.assertIsNone(inquiry.treatment)
		self.assertFalse(os.path.exists(image_path))

	def test_doctor_can_delete_location_and_keep_existing_inquiries(self):
		location = Location.objects.create(name='Whitefield Clinic')
		inquiry = PatientInquiry.objects.create(
			treatment=None,
			location=location,
			full_name='Patient Two',
			phone_number='9876543211',
			email='patient@example.com',
		)
		self.client.force_login(self.doctor)

		response = self.client.post(
			reverse('doctor_catalog'),
			{'section': 'delete_location', 'location_id': location.pk},
			follow=True,
		)

		self.assertRedirects(response, reverse('doctor_catalog'))
		self.assertContains(response, 'Location removed successfully: Whitefield Clinic.')
		self.assertFalse(Location.objects.filter(pk=location.pk).exists())
		inquiry.refresh_from_db()
		self.assertIsNone(inquiry.location)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminOTPLoginTests(TestCase):
	def setUp(self):
		self.admin_group, _ = Group.objects.get_or_create(name='Administrators')
		self.admin_user = get_user_model().objects.create_superuser(
			username='site-admin',
			email='admin@example.com',
			password='test-password-123',
		)
		self.admin_user.groups.add(self.admin_group)
		self.admin_user.groups.add(Group.objects.get_or_create(name='Doctors')[0])

	def test_bad_credentials_show_popup_and_do_not_send_otp(self):
		response = self.client.post(reverse('admin_login'), {
			'username': 'site-admin',
			'password': 'wrong-password',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Username or password is incorrect')
		self.assertEqual(len(mail.outbox), 0)
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	def test_doctor_staff_account_cannot_start_admin_otp(self):
		get_user_model().objects.create_user(
			username='doctor-staff',
			email='doctor@example.com',
			password='test-password-123',
			is_staff=True,
		)
		Group.objects.get_or_create(name='Doctors')[0].user_set.add(
			get_user_model().objects.get(username='doctor-staff')
		)
		response = self.client.post(reverse('admin_login'), {
			'username': 'doctor-staff',
			'password': 'test-password-123',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'cannot access admin')
		self.assertEqual(len(mail.outbox), 0)

	def test_correct_credentials_require_email_otp_before_admin_access(self):
		response = self.client.post(reverse('admin_login'), {
			'username': 'site-admin',
			'password': 'test-password-123',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Enter your email sign-in code')
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, ['admin@example.com'])
		self.assertFalse(response.wsgi_request.user.is_authenticated)

		self.assertIn('Physio Whitefield', mail.outbox[0].subject)
		self.assertIn('one-time code', mail.outbox[0].body)
		self.assertEqual(mail.outbox[0].alternatives[0][1], 'text/html')
		otp = mail.outbox[0].body.split('Your one-time code: ', 1)[1].splitlines()[0]
		response = self.client.post(reverse('admin_login'), {
			'stage': 'otp',
			'otp': otp,
			'next': reverse('admin:index'),
		})

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response['Location'], reverse('admin:index'))
		self.assertTrue(response.wsgi_request.user.is_authenticated)
		admin_response = self.client.get(reverse('admin:index'))
		self.assertEqual(admin_response.status_code, 200)
		self.assertContains(admin_response, 'Admin login successful.')
		self.assertEqual(self.client.get(reverse('doctor_catalog')).status_code, 403)

	def test_superuser_without_administrators_group_can_log_in(self):
		self.admin_user.groups.remove(self.admin_group)
		response = self.client.post(reverse('admin_login'), {
			'username': 'site-admin',
			'password': 'test-password-123',
		})

		self.assertContains(response, 'Enter your email sign-in code')
		otp = mail.outbox[0].body.split('Your one-time code: ', 1)[1].splitlines()[0]
		response = self.client.post(reverse('admin_login'), {
			'stage': 'otp',
			'otp': otp,
		})

		self.assertEqual(response.status_code, 302)
		self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

	@override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
	def test_console_mail_backend_tells_admin_where_to_find_the_code(self):
		response = self.client.post(reverse('admin_login'), {
			'username': 'site-admin',
			'password': 'test-password-123',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Check the runserver terminal for the code.')
		self.assertContains(response, 'Enter your email sign-in code')

	def test_incorrect_otp_shows_popup_without_logging_in(self):
		self.client.post(reverse('admin_login'), {
			'username': 'site-admin',
			'password': 'test-password-123',
		})
		response = self.client.post(reverse('admin_login'), {
			'stage': 'otp',
			'otp': 'not-the-code',
		})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'email sign-in code is incorrect')
		self.assertFalse(response.wsgi_request.user.is_authenticated)

	def test_admin_pages_reject_staff_sessions_without_verified_otp(self):
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse('admin:index'))

		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse('admin_login'), response['Location'])

	def test_doctor_group_user_cannot_access_admin_with_verified_marker(self):
		doctor = get_user_model().objects.create_user(
			username='doctor-only',
			password='test-password-123',
			is_staff=True,
		)
		doctor_group, _ = Group.objects.get_or_create(name='Doctors')
		doctor.groups.add(doctor_group)
		self.client.force_login(doctor)
		session = self.client.session
		session['admin_otp_verified_user_id'] = doctor.pk
		session.save()

		response = self.client.get(reverse('admin:index'))

		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse('admin_login'), response['Location'])
