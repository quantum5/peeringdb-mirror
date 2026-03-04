import datetime

from django import template
from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _
from django_peeringdb.models import Carrier, Facility, InternetExchange, Network, Organization

from peeringdb_ui.views.utils import DoNotRender

register = template.Library()


@register.filter
def make_page_title(entity):
    """
    Returns a page title based on an entity instance
    such as a network or organization
    """

    if entity and hasattr(entity, "HandleRef"):
        if entity.HandleRef.tag == "net":
            return f"AS{entity.asn} - {entity.name} - PeeringDB Mirror"
        elif hasattr(entity, "name"):
            return f"{entity.name} - PeeringDB Mirror"


@register.filter
def as_bool(v):
    if not v or v == "0":
        return False
    return True


@register.filter
def is_none(value):
    return type(value) is None


@register.filter
def none_blank(value):
    if value is None:
        return ""
    return value


@register.filter
def dont_render(value):
    return type(value) is DoNotRender


@register.filter
def editable_list_join(value):
    if not value:
        return ""
    return ",".join(value)


@register.filter
def editable_list_value(row):
    if row.get("multiple"):
        if row.get("value"):
            return ", ".join(row.get("value"))
        return ""

    if row.get("value") or row.get("value_label"):
        return _(row.get("value_label", row.get("value")))
    elif row.get("blank") and row.get("value") == "":
        return row.get("blank")
    return ""


@register.filter
def ref_tag(value):
    if hasattr(value, "_handleref"):
        return value._handleref.tag
    elif value == "InternetExchange":
        return InternetExchange.handleref.tag
    elif value == "Network":
        return Network.handleref.tag
    elif value == "Facility":
        return Facility.handleref.tag
    elif value == "Organization":
        return Organization.handleref.tag
    elif value == "Carrier":
        return Carrier.handleref.tag
    return "unknown"


def format_speed(value):
    if value >= 1000000:
        value = value / 10 ** 6
        if not value % 1:
            return f"{value:.0f}T"
        return f"{value:.1f}T"
    elif value >= 1000:
        return f"{value / 10 ** 3:.0f}G"
    else:
        return f"{value:.0f}M"


@register.filter
def pretty_speed(value):
    if not value:
        return ""
    try:
        return format_speed(value)
    except ValueError:
        return value


@register.filter
def checkmark(value):
    return static('checkmark.png' if value else 'checkmark-off.png')


@register.filter
def make_page_title_for_search_result(request):
    """
    Returns a page title to use on the quick search results page
    """

    if request.GET.get("q"):
        return f"{request.GET.get('q')} - PeeringDB Mirror search"


@register.filter
def obj_type(ref_tag):
    obj_types = {
        "org": "Organization",
        "net": "Network",
        "ix": "Internet Exchange",
        "fac": "Facility",
        "carrier": "Carrier",
        "campus": "Campus",
    }
    return obj_types[ref_tag]


@register.filter
def age(dt):
    seconds = (datetime.datetime.now().replace(tzinfo=dt.tzinfo) - dt).total_seconds()
    if seconds < 60:
        return f"{int(seconds)} {_("seconds ago")}"
    elif seconds < 3600:
        return f"{int(seconds / 60)} {_("minutes ago")}"
    elif seconds < 86400:
        return f"{int(seconds / 3600)} {_("hours ago")}"
    else:
        return f"{int(seconds / 86400)} {_("days ago")}"


@register.filter
def ix_routeservers(ix):
    return ix.ixlan_set.first().netixlan_set(manager="handleref").filter(status="ok").filter(is_rs_peer=True).count()


@register.filter
def prefix(ix):
    return ix.ixlan_set.first().ixpfx_set(manager="handleref").filter(status="ok")
