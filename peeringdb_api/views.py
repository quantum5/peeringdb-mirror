from django.db.models import IntegerField, QuerySet
from django.http import JsonResponse
from django.views.generic.detail import BaseDetailView
from django.views.generic.list import BaseListView

from peeringdb_api.serializer import serialize, serialize_many


def format_for_field(field, value):
    if isinstance(field, IntegerField):
        return int(value)

    return value


class PeeringDBListView(BaseListView):
    def get(self, request, *args, **kwargs):
        queryset: QuerySet = self.model.objects.all()

        for k, v in self.request.GET.items():
            _, final_field, _, _ = queryset.query.names_to_path(k.split('__'), self.model._meta)

            try:
                if k.endswith('__in'):
                    value = [format_for_field(final_field, i) for i in v.split(',')]
                else:
                    value = format_for_field(final_field, v)
            except ValueError:
                return JsonResponse({'data': [], 'meta': {'error': 'Entity not found'}}, status=404)

            queryset = queryset.filter(**{k: value})

        return JsonResponse({'data': serialize_many(queryset)})


class PeeringDBDetailView(BaseDetailView):
    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        return JsonResponse({'data': [serialize(obj)]})
