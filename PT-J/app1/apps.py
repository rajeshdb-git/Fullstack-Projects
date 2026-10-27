from django.apps import AppConfig
from django.conf import settings
from django.utils.autoreload import autoreload_started


class App1Config(AppConfig):
    name = 'app1'

    def ready(self):
        if not settings.DEBUG:
            return

        def watch_dotenv(sender, **kwargs):
            env_file = settings.BASE_DIR / '.env'
            if env_file.is_file():
                sender.extra_files.add(env_file)

        autoreload_started.connect(
            watch_dotenv,
            dispatch_uid='app1.watch_dotenv_for_settings_changes',
        )
