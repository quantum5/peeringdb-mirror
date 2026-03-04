from collections import defaultdict

from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from django_peeringdb.models import Campus, CarrierFacility, Facility, InternetExchangeFacility, NetworkFacility

from peeringdb_ui.serializers import CampusSerializer
from peeringdb_ui.views.utils import DoNotRender, format_last_updated_time, view_component, view_http_error_404


def objfac_tuple(objfac_qset, obj):
    data = defaultdict(list)
    for objfac in objfac_qset:
        data[getattr(objfac, obj)].append(objfac.fac)
    return dict(data)


def view_campus(request, pk):
    """
    View campus data for campus specified by id.
    """

    try:
        campus = Campus.objects.get(pk=pk)
    except ObjectDoesNotExist:
        return view_http_error_404(request)

    data = CampusSerializer(campus).data

    dismiss = DoNotRender()

    facilities = Facility.objects.filter(campus=campus)
    ixfac = InternetExchangeFacility.objects.none()
    netfac = NetworkFacility.objects.none()
    carrierfac = CarrierFacility.objects.none()

    # Merge all the related sets into the 'exchanges' QuerySet
    for facility in facilities:
        ixfac = ixfac.union(facility.ixfac_set.filter(status="ok"), all=False)
        netfac = netfac.union(facility.netfac_set(manager="handleref").filter(status="ok"), all=False)
        carrierfac = carrierfac.union(facility.carrierfac_set.filter(status="ok"), all=False)

    carriers = objfac_tuple(carrierfac, "carrier")
    networks = objfac_tuple(netfac, "net")
    exchanges = objfac_tuple(ixfac, "ix")
    org = data.get("org")

    print(carriers.items())
    print(networks)
    print(exchanges)

    data = {
        "id": campus.id,
        "title": data.get("name", dismiss),
        "facilities": facilities,
        "exchanges": exchanges,
        "networks": networks,
        "carriers": carriers,
        "fields": [
            {
                "name": "org",
                "label": _("Organization"),
                "value": org.get("name", dismiss),
                "type": "entity_link",
                "link": f"/org/{org.get('id')}",
            },
            {
                "name": "aka",
                "label": _("Also Known As"),
                "value": data.get("aka", dismiss) or "",
            },
            {
                "name": "name_long",
                "label": _("Long Name"),
                "value": data.get("name_long", dismiss) or "",
            },
            {
                "name": "city",
                "label": _("City"),
                "value": data.get("city", dismiss),
                "readonly": True,
            },
            {
                "type": "url",
                "name": "website",
                "label": _("Company Website"),
                "value": data.get("website", dismiss),
            },
            {
                "name": "country",
                "label": _("Country Code"),
                "value": data.get("country", dismiss),
                "readonly": True,
            },
            {
                "readonly": True,
                "name": "updated",
                "label": _("Last Updated"),
                "value": format_last_updated_time(data.get("updated", dismiss)),
            },
            {
                "name": "notes",
                "label": _("Notes"),
                "help_text": _("Markdown enabled"),
                "type": "fmt-text",
                "value": data.get("notes", dismiss),
            },
        ],
    }

    return view_component(
        request, "campus", data, "Campus", instance=campus
    )
