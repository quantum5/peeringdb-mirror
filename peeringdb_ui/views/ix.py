from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from django_peeringdb.models import InternetExchange, InternetExchangeFacility, Network, NetworkIXLan

from peeringdb_ui.serializers import InternetExchangeSerializer
from peeringdb_ui.stats import get_ix_stats
from peeringdb_ui.views.utils import DoNotRender, field_help, format_last_updated_time, view_component, \
    view_http_error_404


def view_exchange(request, pk):
    """
    View exchange data for exchange specified by id.
    """

    try:
        exchange = InternetExchange.objects.get(pk=pk, status="ok")
    except ObjectDoesNotExist:
        return view_http_error_404(request)

    data = InternetExchangeSerializer(exchange, context={"user": request.user}).data

    networks = (
        NetworkIXLan.handleref.undeleted()
        .select_related("net", "ixlan")
        .order_by("net__name")
        .filter(ixlan__ix=exchange)
    )
    dismiss = DoNotRender()

    facilities = (
        InternetExchangeFacility.handleref.undeleted()
        .select_related("ix", "fac")
        .filter(ix=exchange)
        .order_by("fac__name")
    )

    org = data.get("org")

    ixlan = exchange.ixlan_set.first()
    data = {
        "policy_general_help_text": field_help(Network, "policy_general"),
        "id": exchange.id,
        "title": data.get("name", dismiss),
        "facilities": facilities,
        "networks": networks,
        "peer_count": 0,
        "connections_count": 0,
        "open_peer_count": 0,
        "total_speed": 0,
        "ipv6_percentage": 0,
        "ixlans": exchange.ixlan_set(manager="handleref").filter(status__in=["ok", "pending"]),
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
            {"name": "city", "label": _("City"), "value": data.get("city", dismiss)},
            {
                "name": "country",
                "type": "list",
                "data": "countries_b",
                "label": _("Country"),
                "value": data.get("country", dismiss),
            },
            {
                "name": "region_continent",
                "type": "list",
                "data": "enum/regions",
                "label": _("Continental Region"),
                "value": data.get("region_continent", dismiss),
            },
            {
                "name": "service_level",
                "type": "list",
                "data": "enum/service_level_types_trunc",
                "label": _("Service Level"),
                "value": data.get("service_level", dismiss),
            },
            {
                "name": "terms",
                "type": "list",
                "data": "enum/terms_types_trunc",
                "label": _("Terms"),
                "value": data.get("terms", dismiss),
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
            {"type": "sub", "label": _("Contact Information")},
            {
                "type": "url",
                "name": "website",
                "label": _("Company Website"),
                "value": data.get("website", dismiss),
            },
            {
                "type": "url",
                "name": "url_stats",
                "label": _("Traffic Stats Website"),
                "value": data.get("url_stats", dismiss),
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
                "help_text": field_help(InternetExchange, "tech_phone"),
            },
            {
                "type": "email",
                "name": "policy_email",
                "label": _("Policy Email"),
                "value": data.get("policy_email", dismiss),
            },
            {
                "type": "string",
                "name": "policy_phone",
                "label": _("Policy Phone"),
                "value": data.get("policy_phone", dismiss),
                "help_text": field_help(InternetExchange, "policy_phone"),
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
                "help_text": field_help(InternetExchange, "sales_phone"),
            },
            {
                "type": "url",
                "name": "status_dashboard",
                "label": _("Health Check"),
                "value": data.get("status_dashboard", dismiss),
            },
        ],
        "stats": get_ix_stats(networks, ixlan),
    }

    return view_component(request, "exchange", data, "Exchange", instance=exchange,
                          prefixes=ixlan.ixpfx_set(manager="handleref").filter(status__in=["ok", "pending"]))
