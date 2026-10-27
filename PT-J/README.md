# PT-J

## Local setup on Windows

From the project folder, run these commands in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt  
python manage.py migrate  
python manage.py createsuperuser  
python manage.py runserver  
```

Open <http://127.0.0.1:8000/admin/login/> and sign in with the superuser credentials. A superuser does not need to be added to the `Administrators` group. The login still requires an email OTP; enter an email address when creating the superuser.

For local development, no `.env` file is required. Without SMTP settings, Django prints the OTP email in the `runserver` terminal. Configure SMTP in a local `.env` file to receive the code by email. Do not commit `.env` or production secrets.

### WhatsApp notifications and inbox

The app uses the official Meta WhatsApp Cloud API and sends doctor appointment alerts only with the approved template configured by `WHATSAPP_APPOINTMENT_TEMPLATE`. The template must have one body parameter that accepts the generated appointment summary. This lets the app notify the doctor outside the 24-hour customer service window. Bookings remain successful if Meta rejects a message. The doctor can see notification outcomes in the bookings dashboard and Django admin, and retry pending/skipped alerts with `python manage.py retry_whatsapp_notifications`.

Configure `WHATSAPP_ENABLED=true`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, and `WHATSAPP_DOCTOR_NUMBER` (international number, digits only). Optionally set `WHATSAPP_DOCTOR_NAME` for the greeting. For incoming messages, set `WHATSAPP_WEBHOOK_VERIFY_TOKEN` to a random secret and `WHATSAPP_APP_SECRET` to the Meta app secret. Configure Meta's webhook callback as `https://your-domain/webhooks/whatsapp/`, verify with the same token, and subscribe to the `messages` field. HTTPS is required in production. Webhook POSTs are authenticated with Meta's `X-Hub-Signature-256` HMAC. Authorized doctor users can review inbound and outbound message history at `/doctor/whatsapp/`. Unknown senders are recorded by number only and are not treated as verified patient identities.

Patient appointment and bill updates remain template messages because the business initiates them and a form booking does not establish a service window. These are sent only when the patient opted in. Configure approved Utility templates using `WHATSAPP_PATIENT_APPOINTMENT_TEMPLATE` and `WHATSAPP_PATIENT_BILL_TEMPLATE`, and `WHATSAPP_TEMPLATE_LANGUAGE`. If the required patient templates are unavailable, those messages cannot be sent outside an open customer service window; this project keeps their existing template flow and does not send free-form messages instead.

Required WhatsApp environment variables: `WHATSAPP_ENABLED`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_DOCTOR_NUMBER`, `WHATSAPP_APPOINTMENT_TEMPLATE`, `WHATSAPP_TEMPLATE_LANGUAGE`, `WHATSAPP_DEFAULT_COUNTRY_CODE`, `WHATSAPP_API_VERSION`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`, and `WHATSAPP_APP_SECRET`. `WHATSAPP_DOCTOR_NAME` is optional. Patient template updates use `WHATSAPP_PATIENT_APPOINTMENT_TEMPLATE` and `WHATSAPP_PATIENT_BILL_TEMPLATE`. Keep all credentials in `.env` or the deployment secret store; never commit them.

`python manage.py setup_project` is optional for superuser admin access. Run it if you need the `Administrators` and `Doctors` groups for other staff accounts.

### Playwright browser automation

Install the development browser-test dependency and Chromium:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

Run the booking and doctor-dashboard browser test:

```powershell
python manage.py test app1.playwright_e2e --verbosity 2
```

The test uses an isolated Django test database, creates a booking through the service page, and checks that the doctor dashboard displays its WhatsApp notification status. WhatsApp is disabled during this browser test, so it does not send real messages. The project should have its regular dependencies installed before running it.







## Doctor Portal – Create Login User

The Doctor Portal requires a Django user with:

* A unique username
* A password
* A valid Gmail/email address
* `is_staff = True`
* Membership in the `Doctors` group
* `is_superuser = False`

### 1. Start the Django Shell

From the project folder:

```powershell
python manage.py shell
```

### 2. Create the Doctor User

Run the following code:

```python
from django.contrib.auth.models import User, Group

doctor = User.objects.create_user(
    username='doctor',
    email='doctor@gmail.com',
    password='Doctor@2026'
)

doctor.is_staff = True
doctor.is_superuser = False
doctor.save()

doctors_group = Group.objects.get(name='Doctors')
doctor.groups.add(doctors_group)
```

Replace these values with the actual doctor's details:

```text
username = 'doctor'
email = 'doctor@gmail.com'
password = 'Doctor@2026'
```

### 3. Verify the Doctor User

Run:

```python
print(doctor.username)
print(doctor.email)
print(doctor.is_staff)
print(doctor.is_superuser)
print(list(doctor.groups.values_list('name', flat=True)))
```

The expected result is:

```text
doctor
doctor@gmail.com
True
False
['Doctors']
```

This means:

* `doctor` → username
* `doctor@gmail.com` → email used for OTP
* `True` → staff account
* `False` → not a superuser
* `Doctors` → authorized Doctor Portal group

### 4. If the Username Already Exists

If you get:

```text
IntegrityError: UNIQUE constraint failed: auth_user.username
```

the username already exists.

Retrieve the existing user instead:

```python
from django.contrib.auth.models import User

doctor = User.objects.get(username='doctor')
```

Then update the details:

```python
doctor.email = 'doctor@gmail.com'
doctor.set_password('Doctor@2026')
doctor.is_staff = True
doctor.is_superuser = False
doctor.save()
```

Add the Doctors group:

```python
from django.contrib.auth.models import Group

doctors_group = Group.objects.get(name='Doctors')
doctor.groups.add(doctors_group)
```

### 5. Start the Development Server

Exit the Django shell:

```python
exit()
```

Then run:

```powershell
python manage.py runserver
```

Open the website and click:

**DOCTOR → Login**

Use:

```text
Username: doctor
Password: Doctor@2026
```

### 6. Email OTP

After entering the username and password, the Doctor Portal requires an email OTP.

During local development, the OTP is printed in the terminal running:

```powershell
python manage.py runserver
```

Look for the generated development sign-in code in the terminal and enter it on the login page.

### 7. Important Notes

* The username must be unique.
* Use a valid email address because the email is used for OTP verification.
* The Doctor account must belong to the `Doctors` group.
* The Doctor account must have `is_staff=True`.
* The Doctor account should not belong to the `Administrators` group.
* A Doctor Portal user does **not** need to be a superuser.
* Never commit real passwords, email credentials, API keys, SMTP passwords, or other secrets to GitHub.

### Required Project Groups

Run this once to create the required groups:

```powershell
python manage.py setup_project
```

If the groups already exist, Django will show:

```text
Administrators: already exists
Doctors: already exists
```

This is normal.

### Basic Setup Order

For a fresh local setup:

```powershell
python manage.py migrate
python manage.py setup_project
python manage.py createsuperuser
python manage.py runserver
```

The **superuser** is used for Django administration.

The **Doctor user** is a separate account used to access the Doctor Portal.
