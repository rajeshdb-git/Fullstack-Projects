from django.contrib.auth.views import redirect_to_login
from django.urls import reverse


class AdminOTPRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.path_info.startswith('/admin/') or request.path_info == reverse('admin_login'):
            return None

        verified_user_id = request.session.get('admin_otp_verified_user_id')
        if (
            request.user.is_authenticated
            and request.user.is_staff
            and (
                request.user.is_superuser
                or request.user.groups.filter(name='Administrators').exists()
            )
            and verified_user_id == request.user.pk
        ):
            return None

        return redirect_to_login(request.get_full_path(), login_url=reverse('admin_login'))