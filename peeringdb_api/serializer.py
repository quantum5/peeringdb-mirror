from typing import Union

from django.core.serializers.python import Serializer as PythonSerializer
from django.db.models import Model, QuerySet


class Serializer(PythonSerializer):
    internal_use_only = False

    def start_serialization(self):
        self._result = []

    def get_dump_object(self, obj):
        self._current['id'] = self._value_from_field(obj, obj._meta.pk)
        return self._current

    def end_object(self, obj):
        self._result.append(self.get_dump_object(obj))
        self._current = None

    def getvalue(self):
        return self._result


def serialize_many(objects: Union[QuerySet, list[Model]]) -> list[dict]:
    serializer = Serializer()
    serializer.serialize(objects, many=True)
    return serializer.getvalue()


def serialize(obj: Model) -> dict:
    return serialize_many([obj])[0]
