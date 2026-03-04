import re

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
from django_peeringdb.models import Campus, Carrier, Facility, IXLanPrefix, InternetExchange, Network, NetworkIXLan, \
    Organization
from haystack.inputs import Exact
from haystack.query import SearchQuerySet
from unidecode import unidecode

autocomplete_models = [
    Organization,
    Network,
    InternetExchange,
    Facility,
    Carrier,
]

searchable_models = [
    Organization,
    Network,
    Facility,
    InternetExchange,
    NetworkIXLan,
    IXLanPrefix,
]

ONLY_DIGITS = re.compile(r"^[0-9]+$")
PARTIAL_IPV4_ADDRESS = re.compile(r"^([0-9]{1,3}\.){1,3}([0-9]{1,3})?$")
PARTIAL_IPV6_ADDRESS = re.compile(r"^([0-9A-Fa-f]{1,4}|:):[0-9A-Fa-f:]*$")


def make_asn_query(term):
    return Network.objects.filter(asn__exact=term, status="ok")


def make_ipv4_query(term):
    return NetworkIXLan.objects.filter(ipaddr4__startswith=term, status="ok")


def make_ipv6_query(term):
    return NetworkIXLan.objects.filter(ipaddr6__startswith=term, status="ok")


def valid_partial_ipv4_address(ip):
    return all(0 <= int(s) <= 255 for s in ip.split(".") if len(s) > 0)


def unaccent(v):
    return unidecode(v).lower().strip()


def prepare_term(term):
    try:
        if len(term) == 1:
            int(term)
            term = f"AS{term}"
    except ValueError:
        pass

    return unaccent(term)


def make_autocomplete_query(term, user):
    if not term:
        return SearchQuerySet().none()

    term = prepare_term(term)
    base_query = SearchQuerySet().autocomplete(auto=term).filter(status=Exact("ok"))

    return base_query.models(*autocomplete_models)


def make_search_query(term):
    if not term:
        return SearchQuerySet().none()

    term = unaccent(term)

    if ONLY_DIGITS.match(term):
        return make_asn_query(term)

    if PARTIAL_IPV4_ADDRESS.match(term):
        if valid_partial_ipv4_address(term):
            return make_ipv4_query(term)

    if PARTIAL_IPV6_ADDRESS.match(term):
        return make_ipv6_query(term)

    term_filters = Q(content=term) | Q(content__startswith=term)

    return (
        SearchQuerySet()
        .filter(term_filters, status=Exact("ok"))
        .models(*searchable_models)
    )


def search_result_name(model):
    if isinstance(model, Network):
        return f"{model.name} ({model.asn})"
    elif hasattr(model, 'name'):
        return model.name
    return 'unknown'


def search(term, autocomplete=False, user=None):
    """
    Search searchable objects (ixp, network, facility ...) by term.

    Returns result dict.
    """

    if autocomplete:
        search_query = make_autocomplete_query(term, user)
        limit = settings.SEARCH_RESULTS_AUTOCOMPLETE_LIMIT
        categories = ("fac", "ix", "net", "org", "carrier")
    else:
        search_query = make_search_query(term)
        limit = settings.SEARCH_RESULTS_LIMIT
        categories = ("fac", "ix", "net", "org")

    result = {tag: [] for tag in categories}
    pk_map = {tag: {} for tag in categories}

    for sq in search_query[:limit]:
        if hasattr(sq, "model"):
            categorize(sq, result, pk_map)
        elif sq.HandleRef.tag == "netixlan":
            add_secondary_entries(sq, result, pk_map)
        else:
            append_result(
                sq.HandleRef.tag,
                sq.pk,
                search_result_name(sq),
                sq.org_id,
                None,
                result,
                pk_map,
            )

    return result


def categorize(sq, result, pk_map):
    if getattr(sq, "result_name", None):
        # main entity
        tag = sq.model.HandleRef.tag
        org_id = int(sq.pk) if tag == "org" else sq.org_id
        append_result(tag, int(sq.pk), sq.result_name, org_id, None, result, pk_map)
    else:
        add_secondary_entries(sq, result, pk_map)


def add_secondary_entries(sq, result, pk_map):
    for tag in result.keys():
        if not getattr(sq, f"{tag}_result_name", None):
            continue

        org_id = int(getattr(sq, f"{tag}_org_id", 0))
        name = getattr(sq, f"{tag}_result_name")
        pk = int(getattr(sq, f"{tag}_id", 0))
        sub_name = getattr(sq, f"{tag}_sub_result_name")
        append_result(tag, pk, name, org_id, sub_name, result, pk_map)


def append_result(tag, pk, name, org_id, sub_name, result, pk_map, extra={}):
    if pk in pk_map[tag]:
        return

    pk_map[tag][pk] = True

    result[tag].append(
        {
            "id": pk,
            "name": name,
            "org_id": int(org_id),
            "sub_name": sub_name,
            "extra": extra,
        }
    )


def handle_asn_query(q):
    match = re.match(r"(asn|as)(\d+)", q.lower())

    if match:
        net = Network.objects.filter(asn=match.group(2), status="ok")
        if net.count() == 1:
            return HttpResponseRedirect(f"/net/{net.first().id}")
    return None


def combine_search_results(result: dict) -> list:
    """
    Combines all search results into a single list.

    Args:
        result: Dictionary containing search results by category

    Returns:
        list: Combined search results
    """
    combined_results = []

    categories = [
        InternetExchange._handleref.tag,
        Network._handleref.tag,
        Facility._handleref.tag,
        Organization._handleref.tag,
        Campus._handleref.tag,
        Carrier._handleref.tag,
    ]

    for category in categories:
        if category in result:
            for item in result[category]:
                item["ref_tag"] = category
                if "extra" not in item or "_score" not in item["extra"]:
                    item["extra"] = item.get("extra", {})
                    item["extra"]["_score"] = 0
                if "sponsorship" in item:
                    item["sponsorship"] = item["sponsorship"]
                combined_results.append(item)

    combined_results.sort(key=lambda x: (-x["extra"]["_score"], (x["name"] or "").lower()))

    return combined_results


def get_page_range(paginator, current_page, show_pages=5):
    """
    Calculate which page numbers to show in pagination.
    Args:
    paginator: The paginator instance
    current_page: Current page number
    show_pages: Number of pages to show on each side of current page
    Returns:
    list: Page numbers to display
    """
    total_pages = paginator.num_pages
    current = current_page

    if total_pages <= 2 * show_pages + 1:
        return list(range(1, total_pages + 1))

    if current <= show_pages + 1:
        return list(range(1, 2 * show_pages + 2))

    if current >= total_pages - show_pages:
        return list(range(total_pages - 2 * show_pages, total_pages + 1))

    return list(range(current - show_pages, current + show_pages + 1))


def build_template_environment(result: dict, request, q: list) -> dict:
    query_combined = " ".join(q) if isinstance(q, list) else q

    campus_facilities = {
        fac.id: fac for fac in Facility.objects.exclude(campus_id__isnull=True)
    }

    for tag, rows in list(result.items()):
        for item in rows:
            if tag == "fac" and item["id"] in campus_facilities:
                item["campus"] = campus_facilities[item["id"]].campus_id

    combined_results = combine_search_results(result)

    page_number = int(request.GET.get("page", 1))
    paginator = Paginator(combined_results, 10)
    page_obj = paginator.get_page(page_number)

    visible_page_range = get_page_range(paginator, page_obj.number)

    as_suggestion = None
    if query_combined.isdigit():
        networks = result.get(Network._handleref.tag, [])
        if networks:
            first_net = networks[0]
            if str(first_net.get("extra", {}).get("asn")) == query_combined:
                as_suggestion = first_net

    return {
        "search_ixp": result.get(InternetExchange._handleref.tag),
        "search_net": result.get(Network._handleref.tag),
        "search_fac": result.get(Facility._handleref.tag),
        "search_org": result.get(Organization._handleref.tag),
        "search_campus": result.get(Campus._handleref.tag),
        "search_carrier": result.get(Carrier._handleref.tag),
        "count_ixp": len(result.get(InternetExchange._handleref.tag, [])),
        "count_net": len(result.get(Network._handleref.tag, [])),
        "count_fac": len(result.get(Facility._handleref.tag, [])),
        "count_org": len(result.get(Organization._handleref.tag, [])),
        "count_campus": len(result.get(Campus._handleref.tag, [])),
        "count_carrier": len(result.get(Carrier._handleref.tag, [])),
        "combined_results": page_obj,
        "visible_page_range": visible_page_range,
        "total_results": len(combined_results),
        "query_combined": query_combined,
        "as_suggestion": as_suggestion,
    }


def request_search(request):
    q = request.GET.get("q")
    print(q)

    # Redirect if no valid query
    if not q:
        return HttpResponseRedirect("/")

    # Handle direct ASN or AS queries
    asn_redirect = handle_asn_query(q)
    if asn_redirect:
        return asn_redirect

    # Perform the search based on the query and version
    result = search(q)

    # Build the environment for rendering the template
    env = build_template_environment(result, request, q)
    template = get_template("site/search_result.html")

    return HttpResponse(template.render(env, request))
