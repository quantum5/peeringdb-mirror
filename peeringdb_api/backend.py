import zoneinfo

from django.db.models import DateTimeField, Model
from django.utils import timezone
from django_peeringdb import __version__  # noqa
from django_peeringdb.client_adaptor.backend import Backend as OldBackend

utc = zoneinfo.ZoneInfo('UTC')


class Backend(OldBackend):
    def clean(self, obj: Model):
        for field in obj._meta.get_fields():
            if isinstance(field, DateTimeField):
                value = getattr(obj, field.name)
                if value and timezone.is_naive(value):
                    setattr(obj, field.name, timezone.make_aware(value, utc))

        super().clean(obj)
