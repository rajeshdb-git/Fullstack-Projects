from .models import ContactQuery, Treatment, WebContacts


def treatment_navigation(request):
	is_doctor_portal = (
		request.path_info.startswith('/doctor/')
		and request.user.is_authenticated
		and request.user.is_staff
		and request.user.groups.filter(name='Doctors').exists()
		and not request.user.groups.filter(name='Administrators').exists()
	)
	context = {
		'nav_treatments': Treatment.objects.order_by('name'),
		'is_doctor_portal': is_doctor_portal,
	}
	if is_doctor_portal:
		context['new_contact_count'] = ContactQuery.objects.filter(
			status=ContactQuery.Status.NEW
		).count()
	return context


def web_contacts(request):
	return {'web_contact': WebContacts.objects.first()}
