from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from django_peeringdb.models import Network, NetworkContact, Organization

from peeringdb_ui.serializers import OrganizationSerializer
from peeringdb_ui.views.utils import DoNotRender, field_help, format_last_updated_time, view_component, \
    view_http_error_404


def view_organization(request, pk):
    """
    View organization data for org specified by id.
    """

    try:
        org = OrganizationSerializer.prefetch_related(
            Organization.objects, request, depth=2
        ).get(pk=pk, status="ok")
    except ObjectDoesNotExist:
        return view_http_error_404(request)

    data = OrganizationSerializer(org).data

    exchanges = data["ix_set"]
    facilities = data["fac_set"]
    networks = data["net_set"]
    carriers = org.carrier_set.filter(status__in=["ok"])
    campuses = org.campus_set.filter(status__in=["ok"])

    dismiss = DoNotRender()

    data = {
        "title": data.get("name", dismiss),
        "exchanges": exchanges,
        "networks": networks,
        "facilities": facilities,
        "carriers": carriers,
        "campuses": campuses,
        "fields": [
            {
                "name": "aka",
                "label": _("Also Known As"),
                "value": data.get("aka", dismiss),
                "notify_incomplete": False,
            },
            {
                "name": "name_long",
                "label": _("Long Name"),
                "value": data.get("name_long", dismiss),
                "notify_incomplete": False,
            },
            {
                "name": "website",
                "type": "url",
                "notify_incomplete": True,
                "value": data.get("website", dismiss),
                "label": _("Website"),
            },
            {
                "name": "address1",
                "label": _("Address 1"),
                "notify_incomplete": True,
                "value": data.get("address1", dismiss),
            },
            {
                "name": "address2",
                "label": _("Address 2"),
                "value": data.get("address2", dismiss),
            },
            {
                "name": "floor",
                "label": _("Floor"),
                # needs to be or to catch "" and None
                "value": (data.get("floor") or dismiss),
                "deprecated": _(
                    "Please move this data to the suite field and remove it from here."
                ),
                "notify_incomplete": False,
            },
            {"name": "suite", "label": _("Suite"), "value": data.get("suite", dismiss)},
            {
                "name": "location",
                "label": _("Location"),
                "type": "location",
                "notify_incomplete": True,
                "value": data,
            },
            {
                "name": "country",
                "type": "list",
                "data": "countries_b",
                "label": _("Country Code"),
                "notify_incomplete": True,
                "value": data.get("country", dismiss),
            },
            {
                "name": "geocode",
                "label": _("Geocode"),
                "type": "geocode",
                "value": data,
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

    data["phone_help_text"] = field_help(NetworkContact, "phone")
    data["info_traffic_help_text"] = field_help(Network, "info_traffic")

    return view_component(request, "organization", data, "Organization", instance=org)
