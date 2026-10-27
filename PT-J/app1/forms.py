from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from .models import (
    ContactQuery,
    Location,
    PatientBill,
    PatientInquiry,
    Treatment,
    WebContacts,
)

MAX_TREATMENT_IMAGE_SIZE = 5 * 1024 * 1024


class PatientInquiryForm(forms.ModelForm):
    treatment = forms.ModelChoiceField(
        queryset=Treatment.objects.all().order_by('name'),
        empty_label='Select a treatment',
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    phone_number = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your phone number',
            'type': 'tel',
            'autocomplete': 'tel',
            'inputmode': 'numeric',
            'pattern': '[0-9]{10}',
            'minlength': '10',
            'title': 'Enter exactly 10 digits.',
        }),
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all().order_by('name'),
        empty_label='Select a location',
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    whatsapp_consent = forms.BooleanField(
        required=False,
        label='I agree to receive appointment and bill updates on WhatsApp.',
    )

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name')
        if full_name:
            full_name = full_name.strip()
        if not full_name:
            raise ValidationError('This field is required.')
        return full_name

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if (
            len(phone_number) != 10
            or not phone_number.isascii()
            or not phone_number.isdigit()
        ):
            raise ValidationError('Enter exactly 10 digits.')
        if PatientInquiry.objects.filter(phone_number=phone_number).exclude(
            pk=self.instance.pk
        ).exists():
            raise ValidationError(
                'This phone number is already booked. Please use a different number.'
            )
        return phone_number

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip()
        if not email:
            raise ValidationError('This field is required.')
        return email

    class Meta:
        model = PatientInquiry
        fields = [
            'full_name',
            'phone_number',
            'email',
            'whatsapp_consent',
            'treatment',
            'location',
            'problems',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter your full name',
                'autocomplete': 'name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter your email address',
                'autocomplete': 'email',
            }),
            'problems': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Briefly describe what you would like help with (optional)',
            }),
        }


class DoctorAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if (not user.is_staff or not user.groups.filter(name='Doctors').exists() or user.groups.filter(name='Administrators').exists()):
            raise ValidationError('This account is not authorized for the doctor portal.')


class TreatmentForm(forms.ModelForm):
    description = forms.CharField(
        required=True,
        help_text='Shown to patients on this treatment page.',
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 5,
            'placeholder': 'Describe this treatment and what patients can expect.',
        }),
    )
    image = forms.ImageField(
        required=True,
        help_text='Required for new treatments. Maximum file size: 5 MB.',
        widget=forms.ClearableFileInput(attrs={'class': 'form-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['image'].required = False

    class Meta:
        model = Treatment
        fields = ['name', 'description', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if Treatment.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError('A treatment with this name already exists.')
        return name

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and image.size > MAX_TREATMENT_IMAGE_SIZE:
            raise ValidationError('Image size must be 5 MB or less.')
        return image


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def clean_name(self):
        return self.cleaned_data['name'].strip()


class PatientBillForm(forms.ModelForm):
    class Meta:
        model = PatientBill
        fields = ['service_description', 'amount', 'notes']
        widgets = {
            'service_description': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Treatment or service billed',
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0.01',
                'step': '0.01',
                'placeholder': '0.00',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 2,
                'placeholder': 'Optional billing notes',
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise ValidationError('Enter a bill amount greater than zero.')
        return amount


class PatientAppointmentForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        appointment_date = cleaned_data.get('appointment_date')
        appointment_time = cleaned_data.get('appointment_time')
        if status == PatientInquiry.Status.SCHEDULED and (
            not appointment_date or not appointment_time
        ):
            raise ValidationError(
                'Enter both an appointment date and time before scheduling.'
            )
        if (
            status == PatientInquiry.Status.SCHEDULED
            and appointment_date
            and appointment_time
        ):
            conflict = (
                PatientInquiry.objects.filter(
                    appointment_date=appointment_date,
                    appointment_time=appointment_time,
                    status=PatientInquiry.Status.SCHEDULED,
                )
                .exclude(pk=self.instance.pk or 0)
                .first()
            )
            if conflict:
                raise ValidationError(
                    'That date and time are already booked for '
                    f'{conflict.full_name} ({conflict.booking_number}). '
                    'Choose another slot.'
                )
        return cleaned_data

    class Meta:
        model = PatientInquiry
        fields = ['appointment_date', 'appointment_time', 'status']
        widgets = {
            'appointment_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
            }),
            'appointment_time': forms.TimeInput(attrs={
                'class': 'form-input',
                'type': 'time',
            }),
            'status': forms.Select(attrs={'class': 'form-input'}),
        }


### Contact Form  >>>>>>>>>>>>>>>>>
class ContactQueryForm(forms.ModelForm):

    agree = forms.BooleanField(
        required=True,
        label='I agree to be contacted regarding my enquiry.'
    )

    class Meta:
        model = ContactQuery

        fields = [
            'first_name',
            'last_name',
            'phone_number',
            'message',
            'agree',
        ]

        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter your first name',
                'autocomplete': 'given-name',
            }),

            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter your last name',
                'autocomplete': 'family-name',
            }),

            'phone_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter your phone number',
                'autocomplete': 'tel',
                'inputmode': 'tel',
            }),

            'message': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Tell us how we can help you...',
                'rows': 5,
            }),
        }

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')

        if not phone_number:
            raise ValidationError('Phone number is required.')

        phone_number = phone_number.strip()

        digits = ''.join(
            ch for ch in phone_number
            if ch.isdigit()
        )

        if len(digits) < 10:
            raise ValidationError(
                'Enter a valid phone number with at least 10 digits.'
            )

        if any(ch.isalpha() for ch in phone_number):
            raise ValidationError(
                'Enter a valid phone number using digits and optional +, spaces, or hyphens.'
            )

        return phone_number
# Update the web contact details
class WebContactsForm(forms.ModelForm):
    class Meta:
        model = WebContacts
        fields = ["gmail", "mobile_number"]
