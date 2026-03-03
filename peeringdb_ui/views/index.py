from django.http import HttpResponse
from django.template.loader import get_template
from django_peeringdb.models import Carrier, Facility, InternetExchange, Network


def view_index(request):
    template = get_template("site/index.html")

    recent = {
        "net": Network.handleref.filter(status="ok").order_by("-updated")[:5],
        "fac": Facility.handleref.filter(status="ok").order_by("-updated")[:5],
        "ix": InternetExchange.handleref.filter(status="ok").order_by("-updated")[:5],
        "carrier": Carrier.handleref.filter(status="ok").order_by("-updated")[:5],
    }

    return HttpResponse(template.render({"recent": recent}, request))