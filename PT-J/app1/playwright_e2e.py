from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from playwright.sync_api import expect, sync_playwright

from .models import Location, PatientInquiry, Treatment, WhatsAppNotification


@override_settings(WHATSAPP_ENABLED=False)
class BookingWhatsAppDashboardBrowserTests(StaticLiveServerTestCase):
	"""Browser test for booking submission and visible WhatsApp status."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.playwright = sync_playwright().start()
		cls.browser = cls.playwright.chromium.launch(headless=True)

	@classmethod
	def tearDownClass(cls):
		cls.browser.close()
		cls.playwright.stop()
		super().tearDownClass()

	@classmethod
	def setUpTestData(cls):
		cls.treatment = Treatment.objects.create(name='Browser Test Therapy')
		cls.location = Location.objects.create(name='Browser Test Clinic')
		group, _ = Group.objects.get_or_create(name='Doctors')
		cls.doctor = get_user_model().objects.create_user(
			username='playwright-doctor',
			email='playwright-doctor@example.test',
			password='test-only-password',
			is_staff=True,
		)
		cls.doctor.groups.add(group)

	def setUp(self):
		self.context = self.browser.new_context()
		self.page = self.context.new_page()

		self.client.force_login(self.doctor)
		session_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
		self.context.add_cookies([{
			'name': settings.SESSION_COOKIE_NAME,
			'value': session_cookie.value,
			'url': self.live_server_url,
		}])

	def tearDown(self):
		self.context.close()

	def test_patient_booking_shows_whatsapp_notification_status_to_doctor(self):
		self.page.goto(f'{self.live_server_url}/services/knee-pain/')
		form = self.page.locator('form.patient-form')
		form.locator('[name="full_name"]').fill('Playwright Booking Patient')
		form.locator('[name="phone_number"]').fill('9876501234')
		form.locator('[name="email"]').fill('playwright-patient@example.test')
		form.locator('[name="treatment"]').select_option(str(self.treatment.pk))
		form.locator('[name="location"]').select_option(str(self.location.pk))
		form.locator('[name="problems"]').fill('Browser automation booking')
		form.locator('button[type="submit"]').click()

		expect(self.page).to_have_url(f'{self.live_server_url}/services/knee-pain/?success=1')
		expect(self.page.get_by_text('Appointment booked successfully.', exact=False)).to_be_visible()

		booking = PatientInquiry.objects.get(full_name='Playwright Booking Patient')
		notification = WhatsAppNotification.objects.get(inquiry=booking)
		self.assertEqual(notification.status, WhatsAppNotification.Status.SKIPPED)
		self.assertEqual(notification.last_reason, 'disabled')

		self.page.goto(f'{self.live_server_url}{reverse("doctor_bookings")}')
		booking_card = self.page.locator('.doctor-booking-card').filter(
			has_text='Playwright Booking Patient'
		)
		expect(booking_card).to_contain_text('Alert skipped')
		expect(booking_card).to_contain_text('Disabled')

		booking_card.get_by_role('link', name='Manage booking').click()
		expect(self.page.get_by_text('Doctor WhatsApp alert')).to_be_visible()
		expect(self.page.locator('dd').filter(has_text='Skipped')).to_be_visible()
