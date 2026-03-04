from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from django_peeringdb.models import Carrier, CarrierFacility

from peeringdb_ui.serializers import CarrierSerializer
from peeringdb_ui.views.utils import DoNotRender, format_last_updated_time, view_component, view_http_error_404


def view_carrier(request, pk):
    """
    View carrier data for carrier specified by id.
    """

    try:
        carrier = Carrier.objects.get(pk=pk, status="ok")
    except ObjectDoesNotExist:
        return view_http_error_404(request)

    data = CarrierSerializer(carrier).data

    dismiss = DoNotRender()

    facilities = (
        CarrierFacility.handleref.undeleted()
        .select_related("carrier", "fac")
        .filter(carrier=carrier)
        .order_by("fac__name")
    )

    org = data.get("org")

    data = {
        "id": carrier.id,
        "title": data.get("name", dismiss),
        "facilities": facilities,
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
                "value": data.get("aka", dismiss),
            },
            {
                "name": "name_long",
                "label": _("Long Name"),
                "value": data.get("name_long", dismiss),
            },
            {
                "type": "url",
                "name": "website",
                "label": _("Company Website"),
                "value": data.get("website", dismiss),
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
        request, "carrier", data, "Carrier", instance=carrier
    )
