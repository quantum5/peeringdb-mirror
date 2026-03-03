from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from django_peeringdb.models import Campus, CarrierFacility, Facility, InternetExchangeFacility, NetworkFacility

from peeringdb_ui.serializers import FacilitySerializer, OrganizationSerializer
from peeringdb_ui.stats import get_fac_stats
from peeringdb_ui.views.utils import BOOL_CHOICE_WITH_OPT_OUT, DoNotRender, field_help, format_last_updated_time, \
    view_component, \
    view_http_error_404


def view_facility(request, pk):
    """
    View facility data for facility specified by id.
    """

    try:
        facility = Facility.objects.get(pk=pk, status="ok")
    except ObjectDoesNotExist:
        return view_http_error_404(request)

    data = FacilitySerializer(facility, context={"user": request.user}).data

    org = OrganizationSerializer(facility.org, context={"user": request.user}).data

    exchanges = (
        InternetExchangeFacility.handleref.undeleted()
        .filter(fac=facility)
        .select_related("ix")
        .order_by("ix__name")
        .all()
    )
    peers = (
        NetworkFacility.handleref.undeleted()
        .filter(fac=facility)
        .select_related("net")
        .order_by("net__name")
    )
    carriers = (
        CarrierFacility.handleref.undeleted()
        .filter(fac=facility)
        .select_related("carrier")
        .order_by("carrier__name")
    )

    dismiss = DoNotRender()

    if facility.campus_id and facility.campus.status == "ok":
        campus_name = facility.campus.name
        campus_id = facility.campus.id
    else:
        campus_name = None
        campus_id = 0

    campuses = Campus.objects.filter(fac_set=facility, status="ok")

    data = {
        "title": data.get("name", dismiss),
        "exchanges": exchanges,
        "peers": peers,
        "carriers": carriers,
        "campuses": campuses,
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
                "value": data.get("website", dismiss),
                "label": _("Company Website"),
            },
            {
                "name": "address1",
                "label": _("Address 1"),
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
                "value": data,
            },
            {
                "name": "country",
                "type": "list",
                "data": "countries_b",
                "label": _("Country Code"),
                "value": data.get("country", dismiss),
            },
            {
                "name": "region_continent",
                "type": "list",
                "data": "enum/regions",
                "label": _("Continental Region"),
                "value": data.get("region_continent", dismiss),
                "readonly": True,
            },
            {
                "name": "campus",
                "type": "entity_link",
                "label": _("Campus"),
                "value": (campus_name or dismiss),
                "link": f"/{Campus._handleref.tag}/{campus_id}",
                "help_text": _("Facility is part of a campus"),
            },
            {
                "name": "geocode",
                "label": _("Geocode"),
                "type": "geocode",
                "value": data,
            },
            {
                "name": "clli",
                "label": _("CLLI Code"),
                "value": data.get("clli", dismiss),
            },
            {
                "name": "npanxx",
                "label": _("NPA-NXX"),
                "value": data.get("npanxx", dismiss),
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
            {
                "type": "email",
                "name": "tech_email",
                "label": _("Technical Email"),
                "value": data.get("tech_email", dismiss),
            },
            {
                "type": "string",
                "name": "tech_phone",
                "label": _("Technical Phone"),
                "value": data.get("tech_phone", dismiss),
                "help_text": field_help(Facility, "tech_phone"),
            },
            {
                "type": "email",
                "name": "sales_email",
                "label": _("Sales Email"),
                "value": data.get("sales_email", dismiss),
            },
            {
                "type": "string",
                "name": "sales_phone",
                "label": _("Sales Phone"),
                "value": data.get("sales_phone", dismiss),
                "help_text": field_help(Facility, "sales_phone"),
            },
            {
                "name": "property",
                "type": "list",
                "data": "enum/property",
                "label": _("Property"),
                "value": data.get("property", dismiss),
                "help_text": field_help(Facility, "property"),
            },
            {
                "name": "diverse_serving_substations",
                "type": "list",
                "data": "enum/bool_choice_with_opt_out_str",
                "label": _("Diverse Serving Substations"),
                "value": data.get("diverse_serving_substations", dismiss),
                "value_label": dict(BOOL_CHOICE_WITH_OPT_OUT).get(
                    data.get("diverse_serving_substations")
                ),
                "help_text": field_help(Facility, "diverse_serving_substations"),
            },
            {
                "name": "available_voltage_services",
                "type": "list",
                "multiple": True,
                "data": "enum/available_voltage",
                "label": _("Available Voltage Services"),
                "value": data.get("available_voltage_services", dismiss),
                "help_text": field_help(Facility, "available_voltage_services"),
            },
            {
                "name": "status_dashboard",
                "type": "url",
                "value": data.get("status_dashboard", dismiss),
                "label": _("Health Check"),
            },
        ],
        "stats": get_fac_stats(peers, exchanges)
    }

    return view_component(
        request,
        "facility",
        data,
        "Facility",
        instance=facility,
    )
