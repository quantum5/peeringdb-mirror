from django.http import HttpResponse, HttpResponseNotFound
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

BOOL_CHOICE = ((False, _("No")), (True, _("Yes")))

BOOL_CHOICE_WITH_OPT_OUT = (
    (None, _("Not Disclosed")),
    (False, _("No")),
    (True, _("Yes")),
)


def view_http_error_404(request):
    template = get_template(request, "site/error_404.html")
    return HttpResponseNotFound(template.render({}, request))


def field_help(model, field):
    """
    Helper function return help_text of a model
    field.
    """
    return model._meta.get_field(field).help_text


def format_last_updated_time(last_updated_time):
    if last_updated_time is None:
        return ""
    elif isinstance(last_updated_time, str):
        return last_updated_time.split(".")[0].rstrip("Z") + "Z"


class DoNotRender:
    """
    Instance of this class is sent when a component attribute does not exist,
    this can then be type checked in the templates to remove non existant attribute
    rows while still allowing attributes with nonetype values to be rendered.
    """

    def all(self):
        return []


def view_component(
        request, component, data, title, perms=None, instance=None, **kwargs
):
    """
    Generic component view.
    """
    if not perms:
        perms = {}

    template = get_template("site/view.html")

    env = {}
    env.update(
        {
            "data": data,
            "permissions": perms,
            "title": title,
            "component": component,
            "instance": instance,
            "ref_tag": instance._handleref.tag,
            "asset_template_name": f"site/view_{component}_assets.html",
            "tools_template_name": f"site/view_{component}_tools.html",
            "side_template_name": f"site/view_{component}_side.html",
            "bottom_template_name": f"site/view_{component}_bottom.html",
        }
    )

    if component == "campus":
        env.update(
            {
                "facilities_template_name": f"site/view_{component}_facilities.html",
                "carriers_template_name": f"site/view_{component}_carriers.html",
                "exchanges_template_name": f"site/view_{component}_exchanges.html",
                "networks_template_name": f"site/view_{component}_networks.html",
            }
        )

    env.update(**kwargs)
    return HttpResponse(template.render(env, request))
