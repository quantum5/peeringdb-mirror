from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _
from django_peeringdb.models import Network, NetworkContact, NetworkFacility, NetworkIXLan

from peeringdb_ui.serializers import NetworkSerializer
from peeringdb_ui.views.utils import BOOL_CHOICE, DoNotRender, field_help, format_last_updated_time, view_component, \
    view_http_error_404


def view_network(request, pk):
    """
    View network data for network specified by id.
    """
    try:
        network = NetworkSerializer.prefetch_related(
            Network.objects, request, depth=2, selective=["poc_set"]
        ).get(pk=pk, status="ok")
    except ObjectDoesNotExist:
        return view_http_error_404(request)

    network_d = NetworkSerializer(network).data

    facilities = (
        NetworkFacility.handleref.undeleted()
        .select_related("fac")
        .filter(net=network)
        .order_by("fac__name")
    )

    exchanges = (
        NetworkIXLan.handleref.undeleted()
        .select_related("ixlan", "ixlan__ix", "net")
        .filter(net=network)
        .order_by("ixlan__ix__name")
    )

    # This will be passed as default value for keys that don't exist - causing
    # them not to be rendered in the template - also it is fairly
    # safe to assume that no existing keys have been dropped because permission
    # requirements to view them were not met.
    dismiss = DoNotRender()

    org = network_d.get("org")

    notify_incomplete_policy_url = network_d.get("policy_general") not in [
        "Open",
        "No",
    ]

    data = {
        "title": network_d.get("name", dismiss),
        "facilities": facilities,
        "exchanges": exchanges,
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
                "notify_incomplete": False,
                "value": network_d.get("aka", dismiss),
            },
            {
                "name": "name_long",
                "label": _("Long Name"),
                "notify_incomplete": False,
                "value": network_d.get("name_long", dismiss),
            },
            {
                "name": "website",
                "label": _("Company Website"),
                "type": "url",
                "notify_incomplete": True,
                "value": network_d.get("website", dismiss),
            },
            {
                "name": "asn",
                "label": _("ASN"),
                "notify_incomplete": True,
                "value": network_d.get("asn", dismiss),
                "readonly": True,
            },
            {
                "name": "irr_as_set",
                "label": _("IRR as-set/route-set"),
                "help_text": field_help(Network, "irr_as_set"),
                "notify_incomplete": True,
                "value": network_d.get("irr_as_set", dismiss),
            },
            {
                "name": "route_server",
                "type": "url",
                "label": _("Route Server URL"),
                "notify_incomplete": False,
                "value": network_d.get("route_server", dismiss),
            },
            {
                "name": "looking_glass",
                "type": "url",
                "label": _("Looking Glass URL"),
                "notify_incomplete": False,
                "value": network_d.get("looking_glass", dismiss),
            },
            {
                "name": "info_types",
                "type": "list",
                "multiple": True,
                "data": "enum/net_types_multi_choice",
                "label": _("Network Types"),
                "value": network_d.get("info_types", dismiss),
            },
            {
                "name": "info_prefixes4",
                "label": _("IPv4 Prefixes"),
                "type": "number",
                "help_text": _(
                    "Recommended maximum number of IPv4 "
                    "routes/prefixes to be configured on peering "
                    "sessions for this ASN.\n"
                    "Leave blank for not disclosed."
                ),
                "notify_incomplete": True,
                "notify_incomplete_group": "prefixes",
                "value": (
                    int(network_d.get("info_prefixes4"))
                    if network_d.get("info_prefixes4") is not None
                    else ""
                ),
            },
            {
                "name": "info_prefixes6",
                "label": _("IPv6 Prefixes"),
                "type": "number",
                "help_text": _(
                    "Recommended maximum number of IPv6 "
                    "routes/prefixes to be configured on peering "
                    "sessions for this ASN.\n"
                    "Leave blank for not disclosed."
                ),
                "notify_incomplete": True,
                "notify_incomplete_group": "prefixes",
                "value": (
                    int(network_d.get("info_prefixes6"))
                    if network_d.get("info_prefixes6") is not None
                    else ""
                ),
            },
            {
                "name": "info_traffic",
                "type": "list",
                "data": "enum/traffic",
                "blank": _("Not Disclosed"),
                "label": _("Traffic Levels"),
                "help_text": field_help(Network, "info_traffic"),
                "value": network_d.get("info_traffic", dismiss),
            },
            {
                "name": "info_ratio",
                "type": "list",
                "data": "enum/ratios",
                "label": _("Traffic Ratios"),
                "blank": _("Not Disclosed"),
                "value": network_d.get("info_ratio", dismiss),
            },
            {
                "name": "info_scope",
                "type": "list",
                "data": "enum/scopes",
                "blank": _("Not Disclosed"),
                "label": _("Geographic Scope"),
                "value": network_d.get("info_scope", dismiss),
            },
            {
                "type": "flags",
                "label": _("Protocols Supported"),
                "value": [
                    {
                        "name": "info_unicast",
                        "label": _("Unicast IPv4"),
                        "value": network_d.get("info_unicast", False),
                    },
                    {
                        "name": "info_multicast",
                        "label": _("Multicast"),
                        "value": network_d.get("info_multicast", False),
                    },
                    {
                        "name": "info_ipv6",
                        "label": _("IPv6"),
                        "value": network_d.get("info_ipv6", False),
                    },
                    {
                        "name": "info_never_via_route_servers",
                        "label": _("Never via route servers"),
                        "help_text": field_help(
                            Network, "info_never_via_route_servers"
                        ),
                        "value": network_d.get("info_never_via_route_servers", False),
                    },
                ],
            },
            {
                "readonly": True,
                "name": "updated",
                "label": _("Last Updated"),
                "value": format_last_updated_time(network_d.get("updated")),
            },
            {
                "readonly": True,
                "name": "netixlan_updated",
                "label": _("Public Peering Info Updated"),
                "value": format_last_updated_time(network_d.get("netixlan_updated")),
            },
            {
                "readonly": True,
                "name": "netfac_updated",
                "label": _("Peering Facility Info Updated"),
                "value": format_last_updated_time(network_d.get("netfac_updated")),
            },
            {
                "readonly": True,
                "name": "poc_updated",
                "label": _("Contact Info Updated"),
                "value": format_last_updated_time(network_d.get("poc_updated")),
            },
            {
                "name": "notes",
                "label": _("Notes"),
                "help_text": _("Markdown enabled"),
                "type": "fmt-text",
                "value": network_d.get("notes", dismiss),
            },
            {"type": "sub", "admin": True, "label": _("PeeringDB Configuration")},
            {"type": "sub", "label": _("Peering Policy Information")},
            {
                "name": "policy_url",
                "label": _("Peering Policy"),
                "value": network_d.get("policy_url", dismiss),
                "notify_incomplete": notify_incomplete_policy_url,
                "type": "url",
            },
            {
                "name": "policy_general",
                "type": "list",
                "data": "enum/policy_general",
                "label": _("General Policy"),
                "value": network_d.get("policy_general", dismiss),
            },
            {
                "name": "policy_locations",
                "type": "list",
                "data": "enum/policy_locations",
                "label": _("Multiple Locations"),
                "value": network_d.get("policy_locations", dismiss),
            },
            {
                "name": "policy_ratio",
                "type": "list",
                "data": "enum/bool_choice_str",
                "label": _("Ratio Requirement"),
                "value": network_d.get("policy_ratio", dismiss),
                "value_label": dict(BOOL_CHOICE).get(network_d.get("policy_ratio")),
            },
            {
                "name": "policy_contracts",
                "type": "list",
                "data": "enum/policy_contracts",
                "label": _("Contract Requirement"),
                "value": network_d.get("policy_contracts", dismiss),
            },
            {
                "name": "status_dashboard",
                "label": _("Health Check"),
                "value": network_d.get("status_dashboard", dismiss),
                "type": "url",
            },
        ],
        "poc_set": network_d.get("poc_set"),
        "phone_help_text": field_help(NetworkContact, "phone"),
        "poc_hidden": False,
    }

    return view_component(
        request, "network", data, "Network", instance=network
    )
