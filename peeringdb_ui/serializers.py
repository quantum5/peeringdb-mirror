"""
REST API Serializer definitions.
REST API POST / PUT data validators.

New serializers should extend ModelSerializer class, which is a custom extension
of django-rest-framework's ModelSerializer.

Custom ModelSerializer implements logic for the expansion of relationships driven by the `depth` url parameter. The depth parameter indicates how many objects to recurse into.

Special api filtering implementation should be done through the `prepare_query`
method.
"""

import datetime
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db.models import Prefetch
from django.db.models.fields.related import (
    ForwardManyToOneDescriptor,
    ReverseManyToOneDescriptor,
)
from django.db.models.query import QuerySet
from django.http import QueryDict
from django.utils.translation import gettext_lazy as _
from django_handleref.rest.serializers import HandleRefSerializer
from django_inet.rest import IPAddressField, IPNetworkField
from django_peeringdb.const import (
    AVAILABLE_VOLTAGE,
    MTUS,
    NET_TYPES,
    NET_TYPES_MULTI_CHOICE,
    SOCIAL_MEDIA_SERVICES,
)
from django_peeringdb.models import Campus, Carrier, CarrierFacility, Facility, IXLan, IXLanPrefix, InternetExchange, \
    InternetExchangeFacility, \
    Network, NetworkContact, NetworkFacility, \
    NetworkIXLan, Organization
from django_peeringdb.models.abstract import AddressModel
from rest_framework import serializers, validators
from rest_framework.exceptions import ValidationError as RestValidationError

# exclude certain query filters that would otherwise
# be exposed to the api for filtering operations

FILTER_EXCLUDE = [
    # unused
    "org__latitude",
    "org__longitude",
    "ixlan_set__descr",
    "ixlan__descr",
    # private
    "ixlan_set__ixf_ixp_member_list_url",
    "ixlan__ixf_ixp_member_list_url",
    "network__notes_private",
    # internal
    "ixf_import_log_set__id",
    "ixf_import_log_set__created",
    "ixf_import_log_set__updated",
    "ixf_import_log_entries__id",
    "ixf_import_log_entries__action",
    "ixf_import_log_entries__reason",
    "sponsorshiporg_set__id",
    "sponsorshiporg_set__url",
    "partnerships__id",
    "partnerships__url",
    "merged_to__id",
    "merged_to__created",
    "merged_from__id",
    "merged_from__created",
    "affiliation_requests__status",
    "affiliation_requests__created",
    "affiliation_requests__org_name",
    "affiliation_requests__id",
]


def queryable_field_xl(fld):
    """
    Translate <fld>_id into <fld> and also translate fac and net queries into "facility"
    and "network" queries.

    FIXME: should be renamed on model schema.
    """

    if re.match("^.+[^_]_id$", fld):
        # if field name is {rel}_id strip the `_id` suffix

        fld = fld[:-3]

    if fld == "fac":
        # if field name is `fac` rename to `facility`
        # since the model relationship field is called `facility`

        return "facility"

    elif fld == "net":
        # if field name is `net` rename to `network`
        # since the model relationship field is called `network`

        return "network"

    elif re.match("net_(.+)", fld):
        # if field name starts with `net_` rename to `network_`
        # since the model relationship field is called `network`

        return re.sub("^net_", "network_", fld)

    elif re.match("fac_(.+)", fld):
        # if field name starts with `fac_` rename to `facility_`
        # since the model relationship field is called `facility`

        return re.sub("^fac_", "facility_", fld)

    return fld


def single_url_param(params, key, fn=None):
    v = params.get(key)

    if not v:
        return None

    if isinstance(v, list):
        v = v[0]

    try:
        if fn:
            v = fn(v)
    except ValueError:
        raise ValidationError({key: _("Invalid value")})
    except Exception as exc:
        raise ValidationError({key: exc})

    return v


def validate_relation_filter_field(a, b):
    b = queryable_field_xl(b)
    a = queryable_field_xl(a)
    if a == b or a == f"{b}_id" or a.find(f"{b}__") == 0:
        return True
    return False


def get_relation_filters(flds, serializer, **kwargs):
    rv = {}
    for k, v in list(kwargs.items()):
        m = re.match("^(.+)__(lt|lte|gt|gte|contains|startswith|in)$", k)
        if isinstance(v, list) and v:
            v = v[0]
        if m and len(k.split("__")) <= 2:
            r = m.group(1)
            f = m.group(2)
            rx = r.split("__")
            if f == "contains":
                f = "icontains"
            elif f == "startswith":
                f = "istartswith"
            if len(rx) == 2:
                rx[0] = queryable_field_xl(rx[0])
                rx[1] = queryable_field_xl(rx[1])
                r_field = rx[0]
                r = "__".join(rx)
            else:
                r_field = r
                r = queryable_field_xl(r)
            if r_field in flds:
                if f == "in":
                    v = v.split(",")
                rv[r] = {"filt": f, "value": v}
        elif k in flds:
            rv[queryable_field_xl(k)] = {"filt": None, "value": v}
        else:
            rx = k.split("__")

            if len(rx) in [2, 3] and rx[0] in flds:
                rx[0] = queryable_field_xl(rx[0])
                rx[1] = queryable_field_xl(rx[1])
                m = re.match("^(.+)__(lt|lte|gt|gte|contains|startswith|in)$", k)
                f = None
                if m:
                    f = m.group(2)
                if f == "in":
                    v = v.split(",")
                rv["__".join(rx[:2])] = {"filt": f, "value": v}

    return rv


class ExtendedURLField(serializers.URLField):
    def __init__(self, **kwargs):
        schemes = kwargs.pop("schemes", None)
        super().__init__(**kwargs)
        validator = URLValidator(
            message=self.error_messages["invalid"], schemes=schemes
        )
        self.validators = []
        self.validators.append(validator)


class NullableIntegerField(serializers.IntegerField):
    """
    Integer field that handles null values.
    """

    def to_internal_value(self, data):
        if data is None or data == "":
            return None
        return super().to_internal_value(data)


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = (AddressModel,)
        fields = [
            "address1",
            "address2",
            "city",
            "country",
            "state",
            "zipcode",
            "floor",
            "suite",
            "latitude",
            "longitude",
        ]


class ModelSerializer(serializers.ModelSerializer):
    """
    ModelSerializer that provides DB API with custom params.

    Main problem with doing field ops here is data is already fetched, so while
    it's fine for single columns, it doesn't help on speed for fk relationships.
    However data is not yet serialized so there may be some gain.

    Using custom method fields to introspect doesn't work at all, because
    they're not called until they're serialized, and then are called once per row,

    for example
    test_depth = serializers.SerializerMethodField('check_for_fk')
    def check_for_fk(self, obj):
        print("check", type(obj))

    class Meta:
        fields = [
            'test_depth',
            ...

    Best bet so far looks like overloading the single object GET in the model
    view set, and adding on the relationships, but need to GET to GET the fields
    defined yet not included in the query, may have to rewrite the base class,
    which would mean talking to the dev and committing back or we'll have this problem
    every update.

    After testing, the time is all in serialization and transfer, so culling
    related here should be fine.

    arg[0] is a queryset, but seems to have already been evaluated

    Addition Query arguments:
    `fields` comma separated list of only fields to display

        could cull the default list down quite a bit by default and make people ask explicitly for them
        self.Meta.default_fields, but I'm not sure it matters, more testing
    """

    is_model = True
    nested_exclude = []

    id = serializers.IntegerField(read_only=True)
    status = serializers.ReadOnlyField()

    def __init__(self, *args, **kwargs):
        # args[0] is either a queryset or a model
        # kwargs: {u'context': {u'view': <peeringdb.rest.NetworkViewSet object
        # at 0x7fa5604e8410>, u'request': <rest_framework.request.Request
        # object at 0x7fa5604e86d0>, u'format': None}}
        for field_name, field in self.fields.items():
            if isinstance(field, serializers.DateTimeField):
                self.fields[field_name] = RemoveMillisecondsDateTimeField(
                    read_only=True
                )

        try:
            data = args[0]
        except IndexError:
            data = None

        if "request" in kwargs.get("context", {}):
            request = kwargs.get("context").get("request")
        else:
            request = None

        is_list = isinstance(data, QuerySet)
        self.nested_depth = self.depth_from_request(request, is_list)

        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)

        if not request:
            return

        fields = self.context["request"].query_params.get("fields")

        if fields:
            fields = fields.split(",")
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)

    @classmethod
    def queryable_field_xl(self, fld):
        return queryable_field_xl(fld)

    @classmethod
    def is_unique_query(cls, request):
        """
        Check if the request parameters are expected to return a unique entity.
        """

        return "id" in request.GET

    @classmethod
    def queryable_relations(self):
        """
        Returns a list of all second level queryable relation fields.
        """
        rv = []

        for fld in self.Meta.model._meta.get_fields():
            if fld.name in FILTER_EXCLUDE:
                continue

            if (
                    hasattr(fld, "get_internal_type")
                    and fld.get_internal_type() == "ForeignKey"
            ):
                model = fld.related_model
                for _fld in model._meta.get_fields():
                    field_name = f"{fld.name}__{_fld.name}"

                    if field_name in FILTER_EXCLUDE:
                        continue

                    if (
                            hasattr(_fld, "get_internal_type")
                            and _fld.get_internal_type() != "ForeignKey"
                    ):
                        rv.append((field_name, _fld))
        return rv

    @classmethod
    def prefetch_query(cls, qset, request):
        if hasattr(request, "_ctf"):
            qset = qset.filter(**request._ctf)
        return qset

    @classmethod
    def depth_from_request(cls, request, is_list):
        """
        Derive aproporiate depth parameter from request. Max and default depth will vary depending on whether
        result set is a list or single object.

        This will return the depth specified in the request or the next best
        possible depth.
        """
        try:
            if not request:
                raise ValueError("No Request")
            return min(
                int(request.query_params.get("depth", cls.default_depth(is_list))),
                cls.max_depth(is_list),
            )
        except ValueError:
            return cls.default_depth(is_list)

    @classmethod
    def max_depth(cls, is_list):
        """
        Return max depth according to whether resultset is list or single GET.
        """
        if is_list:
            return 3
        return 4

    @classmethod
    def default_depth(cls, is_list):
        """
        Return default depth according to whether resultset is list or single GET.
        """
        if is_list:
            return 0
        return 2

    @classmethod
    def prefetch_related(
            cls,
            qset,
            request,
            prefetch=None,
            related=None,
            nested="",
            depth=None,
            is_list=False,
            single=None,
            selective=None,
    ):
        """
        Prefetch related sets according to depth specified in the request.

        Prefetched set data will be located off the instances in an attribute
        called "<tag>_set_active_prefetched" where tag is the handleref tag
        of the objects the set will be holding.
        """

        if depth is None:
            depth = cls.depth_from_request(request, is_list)

        if prefetch is None:
            prefetch = []
            related = []
        if depth <= 0:
            return qset

        if hasattr(cls.Meta, "fields"):
            for fld in cls.Meta.related_fields:
                # cycle through all related fields declared on the serializer

                o_fld = fld

                # selective is specified, check that field is matched
                # otherwise ignore
                if selective and fld not in selective:
                    continue

                # if the field is not to be rendered, skip it
                if fld not in cls.Meta.fields:
                    continue

                # if we're in list serializer get the actual serializer class
                child = getattr(cls._declared_fields.get(fld), "child", None)
                getter = None

                # there are still a few instances where model and serializer
                # fields differ, net_id -> network_id in some cases for example
                #
                # in order to get the actual model field source we can check
                # the primary key relation ship field on the serializer which
                # has the same name with '_id' prefixed to it
                pk_rel_fld = cls._declared_fields.get(f"{fld}_id")

                # if serializer class specifies a through field name, rename
                # field to that
                if child and child.Meta.through:
                    fld = child.Meta.through

                # if primary key relationship field was found and source differs
                # we want to use that source instead
                elif pk_rel_fld and pk_rel_fld.source != fld:
                    fld = pk_rel_fld.source

                # set is getting its values via a proxy attribute specified
                # in the serializer's Meta class as getter
                getter = getattr(cls.Meta, "getter", None)

                # retrieve the model field for the relationship
                model_field = getattr(cls.Meta.model, fld, None)

                if isinstance(model_field, ReverseManyToOneDescriptor):
                    # nested sets

                    # build field and attribute names to prefetch to, this function will be
                    # called in a nested fashion so it is important we keep an aproporiate
                    # attribute "path" in tact
                    if not nested:
                        src_fld = fld
                        attr_fld = f"{fld}_active_prefetched"
                    else:
                        if getter:
                            src_fld = f"{nested}__{getter}__{fld}"
                        else:
                            src_fld = f"{nested}__{fld}"
                        attr_fld = f"{fld}_active_prefetched"

                    route_fld = f"{src_fld}_active_prefetched"

                    # print "(SET)", src_fld, attr_fld, getattr(cls.Meta.model,
                    # fld).related.related_model

                    # build the Prefetch object

                    prefetch.append(
                        Prefetch(
                            src_fld,
                            queryset=cls.prefetch_query(
                                getattr(
                                    cls.Meta.model, fld
                                ).rel.related_model.objects.filter(status="ok"),
                                request,
                            ),
                            to_attr=attr_fld,
                        )
                    )

                    # expanded objects within sets may contain sets themselves,
                    # so make sure to prefetch those as well
                    cls._declared_fields.get(o_fld).child.prefetch_related(
                        qset,
                        request,
                        related=related,
                        prefetch=prefetch,
                        nested=route_fld,
                        depth=depth - 1,
                        is_list=is_list,
                    )

                elif (
                        isinstance(model_field, ForwardManyToOneDescriptor) and not is_list
                ):
                    # single relations

                    if not nested:
                        src_fld = fld
                        related.append(fld)
                    else:
                        if getter:
                            src_fld = f"{nested}__{getter}__{fld}"
                        else:
                            src_fld = f"{nested}__{fld}"

                    route_fld = src_fld

                    # print "(SINGLE)", fld, src_fld, route_fld, model_field

                    # expanded single realtion objects may contain sets, so
                    # make sure to prefetch those as well

                    field = REFTAG_MAP.get(o_fld)
                    if field:
                        field.prefetch_related(
                            qset,
                            request,
                            single=fld,
                            related=related,
                            prefetch=prefetch,
                            nested=route_fld,
                            depth=depth - 1,
                            is_list=is_list,
                        )

            if not nested:
                # print "prefetching", [p.prefetch_through for p in prefetch]
                # qset = qset.select_related(*related).prefetch_related(*prefetch)
                qset = qset.prefetch_related(*prefetch)
        return qset

    @property
    def is_root(self):
        if not self.parent:
            return True
        if (
                isinstance(self.parent, serializers.ListSerializer)
                and not self.parent.parent
        ):
            return True
        return False

    @property
    def in_list(self):
        return isinstance(self.parent, serializers.ListSerializer)

    @property
    def depth(self):
        par = self
        depth = -1
        nd = getattr(par, "nested_depth", 0)
        while par:
            b = hasattr(par, "is_model")
            depth += 1
            if hasattr(par, "nested_depth"):
                nd = par.nested_depth
            par = par.parent

        return (depth, nd + 1, b)

    @property
    def current_depth(self):
        d, nd, a = self.depth
        return nd - d, d, nd, a

    def to_representation(self, data):
        d, x, y, a = self.current_depth

        # a specified whether or not the serialization root is
        # a signle object or a queryset (e.g GET vs GET /<id>)
        # we need to adjust depth limits accordingly due to drf
        # internal parent - child structuring
        if a:
            k = 2
            j = 1
        else:
            k = 1
            j = 0

        r = self.is_root
        pop_related = False
        return_full = True

        if r:
            # main element
            if d < k:
                pop_related = True

        else:
            # sub element
            if self.in_list:
                # sub element in set
                if d < j:
                    return_full = False
                if d < k:
                    pop_related = True

            else:
                # sub element in property
                if d < j:
                    return_full = False
                if d < k:
                    pop_related = True

            for fld in self.nested_exclude:
                if fld in self.fields:
                    self.fields.pop(fld)

        # if the serialization base is not a single object but a GET all
        # request instead we want to drop certain fields from serialization
        # due to horrible performance - these fields are specified in
        # Meta.list_exclude
        if not a:
            for fld in getattr(self.__class__.Meta, "list_exclude", []):
                if fld in self.fields:
                    self.fields.pop(fld)

        # pop relted fields because of depth limit met
        if pop_related:
            for fld in getattr(self.__class__.Meta, "related_fields", []):
                if fld in self.fields:
                    self.fields.pop(fld)

        # return full object if depth limit allows, otherwise return id
        if return_full:
            return super().to_representation(data)
        else:
            return data.id

    def _render_social_media(self, output):
        """
        Until v3 the `website` field still drives the website url of the object
        but we can start rendering in the `social_media` field as well.
        """

        if "website" in output and "social_media" in output:
            # if website is not set we dont need to do anything

            if not output["website"]:
                return

            # replace the social media website item with the object website entry

            for i, item in enumerate(output["social_media"]):
                if item["service"] == "website":
                    output["social_media"][i]["identifier"] = output["website"]
                    return

            # website was not found in social media, so add it

            output["social_media"].append(
                {"service": "website", "identifier": output["website"]}
            )

    def sub_serializer(self, serializer, data, exclude=None):
        if not exclude:
            exclude = []
        s = serializer(read_only=True)
        s.parent = self
        s.nested_exclude = exclude
        return s.to_representation(data)

    def _unique_filter(self, fld, data):
        for _fld, slz_fld in list(self._declared_fields.items()):
            if fld == slz_fld.source:
                if isinstance(slz_fld, serializers.PrimaryKeyRelatedField):
                    return slz_fld.queryset.get(id=data[_fld])


class RequestAwareListSerializer(serializers.ListSerializer):
    """
    A List serializer that has access to the originating
    request.

    Used as the list serializer class for all nested lists
    so time filters can be applied to the resultset if the _ctf param
    is set in the request.
    """

    @property
    def request(self):
        """
        Retrieve the request from the root serializer.
        """

        par = self
        while par:
            if "request" in par._context:
                return par._context["request"]
            par = par.parent
        return None

    def to_representation(self, data):
        return [self.child.to_representation(self.child.extract(item)) for item in data]


def nested(serializer, exclude=[], getter=None, through=None, **kwargs):
    """
    Use this function to create nested serializer fields. Making
    depth work otherwise while fetching related lists via handlref remains a mystery.
    """

    field_set = [fld for fld in serializer.Meta.fields if fld not in exclude]

    class NestedSerializer(serializer):
        class Meta(serializer.Meta):
            list_serializer_class = RequestAwareListSerializer
            fields = field_set
            orig_name = serializer.__name__

        def extract(self, item):
            if getter:
                return getattr(item, getter)
            return item

    NestedSerializer.__name__ = serializer.__name__
    NestedSerializer.Meta.through = through
    NestedSerializer.Meta.getter = getter

    return NestedSerializer(many=True, read_only=True, **kwargs)


class SocialMediaSerializer(serializers.Serializer):
    """
    Renders the social_media property
    """

    service = serializers.ChoiceField(choices=SOCIAL_MEDIA_SERVICES)
    identifier = serializers.CharField()

    class Meta:
        fields = ["service", "identifier"]


class RemoveMillisecondsDateTimeField(serializers.DateTimeField):
    def to_representation(self, value):
        if value is not None and isinstance(value, datetime.datetime):
            value = value.replace(microsecond=0)
        return super().to_representation(value)


# serializers get their own ref_tag in case we want to define different types
# that aren't one to one with models and serializer turns model into a tuple
# so always lookup the ref tag from the serializer (in fact, do we even need it
# on the model?


class FacilitySerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.Facility

    Possible relationship queries:
      - net_id, handled by prepare_query
      - ix_id, handled by prepare_query
      - org_id, handled by serializer
      - org_name, hndled by prepare_query
    """

    org_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), source="org"
    )
    org_name = serializers.CharField(source="org.name", read_only=True)

    org = serializers.SerializerMethodField()

    campus_id = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.all(), source="campus", allow_null=True, required=False
    )

    campus = serializers.SerializerMethodField()

    suggest = serializers.BooleanField(required=False, write_only=True)

    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    social_media = SocialMediaSerializer(required=False, many=True)
    address1 = serializers.CharField()
    city = serializers.CharField()
    zipcode = serializers.CharField(required=False, allow_blank=True, default="")

    tech_phone = serializers.CharField(required=False, allow_blank=True, default="")
    sales_phone = serializers.CharField(required=False, allow_blank=True, default="")

    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)

    available_voltage_services = serializers.MultipleChoiceField(
        choices=AVAILABLE_VOLTAGE, required=False, allow_null=True
    )

    region_continent = serializers.CharField(read_only=True)

    status_dashboard = serializers.URLField(
        required=False, allow_null=True, allow_blank=True, default=""
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("request") and self.context["request"].method == "POST":
            # make lat and long fields readonly on create
            self.fields["latitude"].read_only = True
            self.fields["longitude"].read_only = True

    class Meta:
        model = Facility

        fields = [
                     "id",
                     "org_id",
                     "org_name",
                     "org",
                     "campus_id",
                     "campus",
                     "name",
                     "aka",
                     "name_long",
                     "website",
                     "social_media",
                     "clli",
                     "rencode",
                     "npanxx",
                     "notes",
                     "suggest",
                     "sales_email",
                     "sales_phone",
                     "tech_email",
                     "tech_phone",
                     "available_voltage_services",
                     "diverse_serving_substations",
                     "property",
                     "region_continent",
                     "status_dashboard",
                 ] + HandleRefSerializer.Meta.fields + AddressSerializer.Meta.fields

        read_only_fields = ["rencode", "region_continent", "logo"]

        related_fields = ["org", "campus"]

        list_exclude = ["org", "campus"]

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        qset = qset.select_related("org")
        filters = get_relation_filters(
            [
                "net_id",
                "net",
                "ix_id",
                "ix",
                "org_name",
                "ix_count",
                "net_count",
                "carrier_count",
            ],
            cls,
            **kwargs,
        )

        for field, e in list(filters.items()):
            for valid in ["net", "ix"]:
                if validate_relation_filter_field(field, valid):
                    fn = getattr(cls.Meta.model, f"related_to_{valid}")
                    qset = fn(qset=qset, field=field, **e)
                    break
            if field == "org_name":
                flt = {f"org__name__{e['filt'] or 'icontains'}": e["value"]}
                qset = qset.filter(**flt)

            if field == "network_count":
                if e["filt"]:
                    flt = {f"net_count__{e['filt']}": e["value"]}
                else:
                    flt = {"net_count": e["value"]}
                qset = qset.filter(**flt)

        if "asn_overlap" in kwargs:
            asns = kwargs.get("asn_overlap", [""])[0].split(",")
            qset = cls.Meta.model.overlapping_asns(asns, qset=qset)
            filters.update({"asn_overlap": kwargs.get("asn_overlap")})

        if "org_present" in kwargs:
            org_list = kwargs.get("org_present")[0].split(",")
            fac_ids = []

            # relation through netfac
            fac_ids.extend(
                [
                    netfac.facility_id
                    for netfac in NetworkFacility.objects.filter(
                    network__org_id__in=org_list
                )
                ]
            )

            # relation through ixfac
            fac_ids.extend(
                [
                    ixfac.facility_id
                    for ixfac in InternetExchangeFacility.objects.filter(
                    ix__org_id__in=org_list
                )
                ]
            )

            qset = qset.filter(id__in=set(fac_ids))

            filters.update({"org_present": kwargs.get("org_present")[0]})

        if "org_not_present" in kwargs:
            org_list = kwargs.get("org_not_present")[0].split(",")
            fac_ids = []

            # relation through netfac
            fac_ids.extend(
                [
                    netfac.facility_id
                    for netfac in NetworkFacility.objects.filter(
                    network__org_id__in=org_list
                )
                ]
            )

            # relation through ixfac
            fac_ids.extend(
                [
                    ixfac.facility_id
                    for ixfac in InternetExchangeFacility.objects.filter(
                    ix__org_id__in=org_list
                )
                ]
            )

            qset = qset.exclude(id__in=set(fac_ids))

            filters.update({"org_not_present": kwargs.get("org_not_present")[0]})

        if "all_net" in kwargs:
            network_id_list = [
                int(net_id) for net_id in kwargs.get("all_net")[0].split(",")
            ]
            qset = cls.Meta.model.related_to_multiple_networks(
                value_list=network_id_list, qset=qset
            )
            filters.update({"all_net": kwargs.get("all_net")})

        if "not_net" in kwargs:
            networks = kwargs.get("not_net")[0].split(",")
            qset = cls.Meta.model.not_related_to_net(
                filt="in", value=networks, qset=qset
            )
            filters.update({"not_net": kwargs.get("not_net")})

        cls.convert_to_spatial_search(kwargs)

        if "distance" in kwargs:
            qset = cls.prepare_spatial_search(
                qset, kwargs, single_url_param(kwargs, "distance", float)
            )

        return qset, filters

    def to_internal_value(self, data):
        # if `suggest` keyword is provided, hard-set the org to
        # whichever org is specified in `SUGGEST_ENTITY_ORG`
        #
        # this happens here so it is done before the validators run
        if isinstance(data, QueryDict):
            data = data.dict()
        if "suggest" in data and (not self.instance or not self.instance.id):
            data["org_id"] = settings.SUGGEST_ENTITY_ORG

        return super().to_internal_value(data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        if not isinstance(representation, dict):
            return representation

        # django-rest-framework multiplechoicefield maintains
        # a set of values and thus looses sorting.
        #
        # we always want to return values sorted by choice
        # definition order
        if instance.available_voltage_services:
            avs = []
            for choice, label in AVAILABLE_VOLTAGE:
                if choice in instance.available_voltage_services:
                    avs.append(choice)

            representation["available_voltage_services"] = avs

        if isinstance(representation, dict) and not representation.get("website"):
            representation["website"] = instance.org.website

        return representation

    def get_org(self, inst):
        return self.sub_serializer(OrganizationSerializer, inst.org)

    def get_campus(self, inst):
        if inst.campus:
            return self.sub_serializer(CampusSerializer, inst.campus)
        else:
            return None


class CarrierFacilitySerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.CarrierFacility
    """

    #  facilities = serializers.PrimaryKeyRelatedField(queryset='fac_set', many=True)

    fac_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(), source="facility"
    )
    carrier_id = serializers.PrimaryKeyRelatedField(
        queryset=Carrier.objects.all(), source="carrier"
    )

    fac = serializers.SerializerMethodField()
    carrier = serializers.SerializerMethodField()

    name = serializers.SerializerMethodField()

    class Meta:
        model = CarrierFacility
        depth = 0
        fields = [
                     "id",
                     "name",
                     "carrier_id",
                     "carrier",
                     "fac_id",
                     "fac",
                 ] + HandleRefSerializer.Meta.fields
        _ref_tag = model.handleref.tag

        related_fields = ["carrier", "fac"]

        list_exclude = ["carrier", "fac"]

        validators = [
            validators.UniqueTogetherValidator(
                CarrierFacility.objects.all(), ["carrier_id", "fac_id"]
            )
        ]

    def get_carrier(self, inst):
        return self.sub_serializer(CarrierSerializer, inst.carrier)

    def get_fac(self, inst):
        return self.sub_serializer(FacilitySerializer, inst.facility)

    def get_name(self, inst):
        return inst.facility.name


class CarrierSerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.Carrier
    """

    carrierfac_set = nested(
        CarrierFacilitySerializer,
        exclude=["fac", "fac"],
        source="carrierfac_set_active_prefetched",
    )

    fac_count = serializers.SerializerMethodField()

    org_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), source="org"
    )
    org_name = serializers.CharField(source="org.name", read_only=True)

    org = serializers.SerializerMethodField()

    social_media = SocialMediaSerializer(required=False, many=True)

    class Meta:
        model = Carrier

        fields = [
                     "id",
                     "org_id",
                     "org_name",
                     "org",
                     "name",
                     "aka",
                     "name_long",
                     "website",
                     "social_media",
                     "notes",
                     "carrierfac_set",
                     "fac_count",
                 ] + HandleRefSerializer.Meta.fields

        related_fields = ["org", "carrierfac_set"]
        list_exclude = ["org"]
        read_only_fields = ["logo"]

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        """
        Allows filtering by indirect relationships, similar to NetworkSerializer.
        """

        qset = qset.prefetch_related(
            "org",
            "carrierfac_set",
        )  # Eagerly load the related Organization# Eagerly load the related Organization

        filters = get_relation_filters(
            [
                "carrierfac_set__facility_id",
                # Add other relevant fields from carrierfac_set here
            ],
            cls,
            **kwargs,
        )

        for field, e in list(filters.items()):
            # Handle filtering based on relationships in carrierfac_set
            if field.startswith("carrierfac_set__"):
                if e["filt"]:
                    filter_kwargs = {f"{field}__{e['filt']}": e["value"]}
                else:
                    filter_kwargs = {field: e["value"]}
                qset = qset.filter(**filter_kwargs)

        return qset, filters

    def get_fac_count(self, inst):
        return inst.carrierfac_set.filter(status="ok").count()

    def get_facilities(self, obj):
        return ", ".join([cf.facility.name for cf in obj.carrierfac_set.all()])

    def get_org(self, inst):
        return self.sub_serializer(OrganizationSerializer, inst.org)

    def to_representation(self, data):
        representation = super().to_representation(data)

        if isinstance(representation, dict) and not representation.get("website"):
            representation["website"] = data.org.website

        return representation


class InternetExchangeFacilitySerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.InternetExchangeFacility

    Possible relationship queries:
      - fac_id, handled by serializer
      - ix_id, handled by serializer
    """

    ix_id = serializers.PrimaryKeyRelatedField(
        queryset=InternetExchange.objects.all(), source="ix"
    )
    fac_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(), source="facility"
    )

    ix = serializers.SerializerMethodField()
    fac = serializers.SerializerMethodField()

    name = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()

    class Meta:
        model = InternetExchangeFacility
        fields = [
                     "id",
                     "name",
                     "city",
                     "country",
                     "ix_id",
                     "ix",
                     "fac_id",
                     "fac",
                 ] + HandleRefSerializer.Meta.fields

        list_exclude = ["ix", "fac"]

        related_fields = ["ix", "fac"]

        validators = [
            validators.UniqueTogetherValidator(
                InternetExchangeFacility.objects.all(), ["ix_id", "fac_id"]
            )
        ]

        _ref_tag = model.handleref.tag

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        qset = qset.select_related("ix", "ix__org", "facility")

        filters = get_relation_filters(["name", "country", "city"], cls, **kwargs)
        for field, e in list(filters.items()):
            for valid in ["name", "country", "city"]:
                if validate_relation_filter_field(field, valid):
                    fn = getattr(cls.Meta.model, f"related_to_{valid}")
                    field = f"facility__{valid}"
                    qset = fn(qset=qset, field=field, **e)
                    break

        return qset, filters

    def get_ix(self, inst):
        return self.sub_serializer(InternetExchangeSerializer, inst.ix)

    def get_fac(self, inst):
        return self.sub_serializer(FacilitySerializer, inst.facility)

    def get_name(self, inst):
        return inst.facility.name

    def get_country(self, inst):
        return inst.facility.country

    def get_city(self, inst):
        return inst.facility.city


class NetworkContactSerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.NetworkContact

    Possible relationship queries:
      - net_id, handled by serializer
    """

    net_id = serializers.PrimaryKeyRelatedField(
        queryset=Network.objects.all(), source="network"
    )
    net = serializers.SerializerMethodField()

    class Meta:
        model = NetworkContact
        depth = 0
        fields = [
                     "id",
                     "net_id",
                     "net",
                     "role",
                     "visible",
                     "name",
                     "phone",
                     "email",
                     "url",
                 ] + HandleRefSerializer.Meta.fields

        related_fields = ["net"]

        list_exclude = ["net"]

        _ref_tag = model.handleref.tag

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        qset = qset.select_related("network", "network__org")
        return qset, {}

    def grainy_namespace_create(self, **kwargs):
        return kwargs["network"].grainy_namespace

    def get_net(self, inst):
        return self.sub_serializer(NetworkSerializer, inst.network)

    def to_representation(self, data):
        # When a network contact is marked as deleted we
        # want to return blank values for any sensitive
        # fields (#569)

        representation = super().to_representation(data)

        if (
                isinstance(representation, dict)
                and representation.get("status") == "deleted"
        ):
            for field in ["name", "phone", "email", "url"]:
                representation[field] = ""

        return representation


class NetworkIXLanSerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.NetworkIXLan

    Possible relationship queries:
      - net_id, handled by serializer
      - ixlan_id, handled by serializer
      - ix_id, handled by prepare_query
      - ixlan_id, handled by serializer
      - ix_side_id, handled by serializer
    """

    net_id = serializers.PrimaryKeyRelatedField(
        queryset=Network.objects.all(), source="network"
    )
    ixlan_id = serializers.PrimaryKeyRelatedField(
        queryset=IXLan.objects.all(), source="ixlan"
    )
    net_side_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(),
        source="net_side",
        allow_null=True,
        required=False,
    )
    ix_side_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(),
        source="ix_side",
        allow_null=True,
        required=False,
    )

    net = serializers.SerializerMethodField()
    ixlan = serializers.SerializerMethodField()

    name = serializers.SerializerMethodField()
    ix_id = serializers.SerializerMethodField()

    ipaddr4 = IPAddressField(version=4, allow_blank=True)
    ipaddr6 = IPAddressField(version=6, allow_blank=True)

    class Meta:
        model = NetworkIXLan
        depth = 0
        fields = [
                     "id",
                     "net_id",
                     "net",
                     "ix_id",
                     "name",
                     "ixlan_id",
                     "ixlan",
                     "notes",
                     "speed",
                     "asn",
                     "ipaddr4",
                     "ipaddr6",
                     "is_rs_peer",
                     "bfd_support",
                     "operational",
                     "net_side_id",
                     "ix_side_id",
                 ] + HandleRefSerializer.Meta.fields

        read_only_fields = ["net_side_id", "ix_side_id"]
        related_fields = ["net", "ixlan"]
        list_exclude = ["net", "ixlan"]

        _ref_tag = model.handleref.tag

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        """
        Allows filtering by indirect relationships.

        Currently supports: ix_id
        """

        qset = qset.select_related("network", "network__org")

        filters = get_relation_filters(["ix_id", "ix", "name"], cls, **kwargs)
        for field, e in list(filters.items()):
            for valid in ["ix", "name"]:
                if validate_relation_filter_field(field, valid):
                    fn = getattr(cls.Meta.model, f"related_to_{valid}")
                    if field == "name":
                        field = "ix__name"
                    qset = fn(qset=qset, field=field, **e)
                    break

        qset = qset.select_related("network", "ixlan", "ixlan__ix")

        return qset, filters

    def get_net(self, inst):
        return self.sub_serializer(NetworkSerializer, inst.network)

    def get_ixlan(self, inst):
        return self.sub_serializer(IXLanSerializer, inst.ixlan)

    def get_name(self, inst):
        ixlan_name = inst.ixlan.name
        if ixlan_name:
            return f"{inst.ix_name}: {ixlan_name}"
        return inst.ix_name

    def get_ix_id(self, inst):
        return inst.ix_id


class NetworkFacilitySerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.NetworkFacility

    Possible relationship queries:
      - fac_id, handled by serializer
      - net_id, handled by seralizers
    """

    fac_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(), source="facility"
    )
    net_id = serializers.PrimaryKeyRelatedField(
        queryset=Network.objects.all(), source="network"
    )

    fac = serializers.SerializerMethodField()
    net = serializers.SerializerMethodField()

    name = serializers.SerializerMethodField()
    country = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()

    class Meta:
        model = NetworkFacility
        depth = 0
        fields = [
                     "id",
                     "name",
                     "city",
                     "country",
                     "net_id",
                     "net",
                     "fac_id",
                     "fac",
                 ] + HandleRefSerializer.Meta.fields
        _ref_tag = model.handleref.tag

        related_fields = ["net", "fac"]

        list_exclude = ["net", "fac"]

        validators = [
            validators.UniqueTogetherValidator(
                NetworkFacility.objects.all(), ["net_id", "fac_id"]
            )
        ]

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        qset = qset.select_related("network", "network__org")

        filters = get_relation_filters(["name", "country", "city"], cls, **kwargs)
        for field, e in list(filters.items()):
            for valid in ["name", "country", "city"]:
                if validate_relation_filter_field(field, valid):
                    fn = getattr(cls.Meta.model, f"related_to_{valid}")
                    field = f"facility__{valid}"
                    qset = fn(qset=qset, field=field, **e)
                    break

        return qset.select_related("network", "facility"), filters

    def get_net(self, inst):
        return self.sub_serializer(NetworkSerializer, inst.network)

    def get_fac(self, inst):
        return self.sub_serializer(FacilitySerializer, inst.facility)

    def get_name(self, inst):
        return inst.facility.name

    def get_country(self, inst):
        return inst.facility.country

    def get_city(self, inst):
        return inst.facility.city


class LegacyInfoTypeField(serializers.Field):
    def to_representation(self, obj):
        return obj

    def to_internal_value(self, data):
        if not data:
            return []
        return [data]

    def validate(self, data):
        if data == "Not Disclosed" or not data:
            return None
        if data not in NET_TYPES:
            raise serializers.ValidationError(
                _("Invalid value for info_type: %(value)s"),
                code="invalid",
                params={"value": data},
            )


class NetworkSerializer(ModelSerializer):
    # TODO override these so they dn't repeat network ID, or add a kwarg to
    # disable fields
    """
    Serializer for peeringdb_server.models.Network

    Possible realtionship queries:
      - org_id, handled by serializer
      - ix_id, handled by prepare_query
      - ixlan_id, handled by prepare_query
      - netfac_id, handled by prepare_query
      - fac_id, handled by prepare_query
    """

    netfac_set = nested(
        NetworkFacilitySerializer,
        exclude=["net_id", "net"],
        source="netfac_set_active_prefetched",
    )

    poc_set = nested(
        NetworkContactSerializer,
        exclude=["net_id", "net"],
        source="poc_set_active_prefetched",
    )

    netixlan_set = nested(
        NetworkIXLanSerializer,
        exclude=["net_id", "net"],
        source="netixlan_set_active_prefetched",
    )

    org_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), source="org"
    )
    org = serializers.SerializerMethodField()

    route_server = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[URLValidator(schemes=["http", "https", "telnet", "ssh"])],
    )

    looking_glass = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[URLValidator(schemes=["http", "https", "telnet", "ssh"])],
    )

    info_prefixes4 = NullableIntegerField(allow_null=True, required=False)
    info_prefixes6 = NullableIntegerField(allow_null=True, required=False)

    suggest = serializers.BooleanField(required=False, write_only=True)

    status_dashboard = serializers.URLField(
        required=False, allow_null=True, allow_blank=True, default=""
    )

    social_media = SocialMediaSerializer(required=False, many=True)

    # irr_as_set = serializers.CharField(validators=[validate_irr_as_set])

    info_types = serializers.MultipleChoiceField(
        choices=NET_TYPES_MULTI_CHOICE, required=False, allow_null=True
    )

    info_type = LegacyInfoTypeField(required=False, allow_null=True)

    class Meta:
        model = Network
        depth = 1
        fields = [
                     "id",
                     "org_id",
                     "org",
                     "name",
                     "aka",
                     "name_long",
                     "website",
                     "social_media",
                     "asn",
                     "looking_glass",
                     "route_server",
                     "irr_as_set",
                     "info_type",
                     "info_types",
                     "info_prefixes4",
                     "info_prefixes6",
                     "info_traffic",
                     "info_ratio",
                     "info_scope",
                     "info_unicast",
                     "info_multicast",
                     "info_ipv6",
                     "info_never_via_route_servers",
                     "notes",
                     "policy_url",
                     "policy_general",
                     "policy_locations",
                     "policy_ratio",
                     "policy_contracts",
                     "netfac_set",
                     "netixlan_set",
                     "poc_set",
                     "suggest",
                     "status_dashboard",
                 ] + HandleRefSerializer.Meta.fields
        default_fields = ["id", "name", "asn"]
        related_fields = [
            "org",
            "netfac_set",
            "netixlan_set",
            "poc_set",
        ]
        read_only_fields = [
            "netixlan_updated",
            "netfac_updated",
            "poc_updated",
            "rir_status",
            "rir_status_updated",
            "logo",
        ]
        list_exclude = ["org"]

        _ref_tag = model.handleref.tag

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        """
        Allows filtering by indirect relationships.

        Currently supports: ixlan_id, ix_id, netixlan_id, netfac_id, fac_id
        """

        qset = qset.select_related("org")

        filters = get_relation_filters(
            [
                "ixlan_id",
                "ixlan",
                "ix_id",
                "ix",
                "netixlan_id",
                "netixlan",
                "netfac_id",
                "netfac",
                "fac",
                "fac_id",
                "fac_count",
                "ix_count",
            ],
            cls,
            **kwargs,
        )

        for field, e in list(filters.items()):
            for valid in ["ix", "ixlan", "netixlan", "netfac", "fac"]:
                if validate_relation_filter_field(field, valid):
                    fn = getattr(cls.Meta.model, f"related_to_{valid}")
                    qset = fn(qset=qset, field=field, **e)
                    break

            if field == "facility_count":
                if e["filt"]:
                    flt = {f"fac_count__{e['filt']}": e["value"]}
                else:
                    flt = {"fac_count": e["value"]}
                qset = qset.filter(**flt)

        # networks that are NOT present at exchange
        if "not_ix" in kwargs:
            not_ix = kwargs.get("not_ix")[0]
            qset = cls.Meta.model.not_related_to_ix(value=not_ix, qset=qset)
            filters.update({"not_ix": not_ix})

        # networks that are NOT present at facility
        if "not_fac" in kwargs:
            not_fac = kwargs.get("not_fac")[0]
            qset = cls.Meta.model.not_related_to_fac(value=not_fac, qset=qset)
            filters.update({"not_fac": not_fac})

        return qset, filters

    @classmethod
    def finalize_query_params(cls, qset, query_params: dict):
        # legacy info_type field needs to be converted to info_types
        # we do this by creating an annotation based on the info_types split by ','

        update_params = {}
        query_adjusted = False

        from django.db.models import Q

        for key, value in query_params.items():
            if key == "info_type":
                # handle direct info_type filter by converting to info_types
                # and doing a direct filter with the same value against
                # info_types checking for startswith, contains, or endswith taking
                # the delimiter into account

                query = (
                        Q(info_types__istartswith=value)
                        | Q(info_types__icontains=f",{value},")
                        | Q(info_types__iendswith=f",{value}")
                )
                qset = qset.filter(query)
                query_adjusted = True

            elif key == "info_type__contains":
                # info_type__contains filter can simply be converted to info_types

                update_params["info_types__contains"] = value
            elif key == "info_type__in" or key == "info_types__in":
                # info_types__in will filter on the info_types field
                # doing an overlap check against the provided values

                query = Q()
                for _value in value.split(","):
                    query |= Q(info_types__icontains=_value.strip())
                qset = qset.filter(query)
                query_adjusted = True

            elif key == "info_type__startswith" or key == "info_types__startswith":
                # info_type__startswith filter can simply be converted to info_types

                query = Q(info_types__istartswith=value) | Q(
                    info_types__icontains=f",{value}"
                )
                qset = qset.filter(query)
                query_adjusted = True
            else:
                update_params[key] = value

        return (qset, update_params, query_adjusted)

    @classmethod
    def is_unique_query(cls, request):
        if "asn" in request.GET:
            return True
        return ModelSerializer.is_unique_query(request)

    def get_org(self, inst):
        return self.sub_serializer(OrganizationSerializer, inst.org)

    def validate_legacy_info_type(self, instance, validated_data):
        # Handle a write to the legacy info_type field (keep API backwards compatible)
        #
        # we still need to be able to handle writes to the legacy
        # info_type field so we need to pop it out of the validated
        legacy_info_type = validated_data.pop("info_type", None)
        if legacy_info_type:
            validated_data["info_types"] = legacy_info_type

    def to_representation(self, data):
        representation = super().to_representation(data)

        if isinstance(representation, dict):
            if not representation.get("website"):
                representation["website"] = data.org.website

            instance = data

            # django-rest-framework multiplechoicefield maintains
            # a set of values and thus looses sorting.
            #
            # we always want to return values sorted by choice
            # definition order

            if instance.info_types:
                sorted_info_types = sorted([x for x in instance.info_types])
                representation["info_types"] = sorted_info_types

            # legacy info_type field informed from info_types
            # using the first value if it exists else empty string

            representation["info_type"] = (
                list(instance.info_types)[0] if instance.info_types else ""
            )

        return representation


# Create an Network serializer with no fields
class ASSetSerializer(NetworkSerializer):
    class Meta:
        model = Network
        fields = []


class IXLanPrefixSerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.IXLanPrefix

    Possible relationship queries:
      - ixlan_id, handled by serializer
      - ix_id, handled by prepare_query
    """

    ixlan_id = serializers.PrimaryKeyRelatedField(
        queryset=IXLan.objects.all(), source="ixlan"
    )

    ixlan = serializers.SerializerMethodField()

    prefix = IPNetworkField()
    in_dfz = serializers.BooleanField(required=False, default=True)

    class Meta:
        model = IXLanPrefix
        fields = [
                     "id",
                     "ixlan",
                     "ixlan_id",
                     "protocol",
                     "prefix",
                     "in_dfz",
                 ] + HandleRefSerializer.Meta.fields

        related_fields = ["ixlan"]

        list_exclude = ["ixlan"]

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        qset = qset.select_related("ixlan", "ixlan__ix", "ixlan__ix__org")

        filters = get_relation_filters(["ix_id", "ix", "whereis"], cls, **kwargs)
        for field, e in list(filters.items()):
            for valid in ["ix"]:
                if validate_relation_filter_field(field, valid):
                    fn = getattr(cls.Meta.model, f"related_to_{valid}")
                    qset = fn(qset=qset, field=field, **e)
                    break

            if field == "whereis":
                qset = cls.Meta.model.whereis_ip(e["value"], qset=qset)

        return qset.select_related("ixlan", "ixlan__ix"), filters

    def get_ixlan(self, inst):
        return self.sub_serializer(IXLanSerializer, inst.ixlan)


class IXLanSerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.IXLan

    Possible relationship queries:
      - ix_id, handled by serializer
    """

    dot1q_support = serializers.SerializerMethodField()

    ix_id = serializers.PrimaryKeyRelatedField(
        queryset=InternetExchange.objects.all(), source="ix"
    )

    ix = serializers.SerializerMethodField()

    net_set = nested(
        NetworkSerializer,
        source="netixlan_set_active_prefetched",
        through="netixlan_set",
        getter="network",
    )
    ixpfx_set = nested(
        IXLanPrefixSerializer,
        exclude=["ixlan_id", "ixlan"],
        source="ixpfx_set_active_prefetched",
    )

    mtu = serializers.ChoiceField(choices=MTUS, required=False, default=1500)

    class Meta:
        model = IXLan
        fields = [
                     "id",
                     "ix_id",
                     "ix",
                     "name",
                     "descr",
                     "mtu",
                     "dot1q_support",
                     "rs_asn",
                     "arp_sponge",
                     "net_set",
                     "ixpfx_set",
                     "ixf_ixp_member_list_url",
                     "ixf_ixp_member_list_url_visible",
                 ] + HandleRefSerializer.Meta.fields
        related_fields = ["ix", "net_set", "ixpfx_set"]

        list_exclude = ["ix"]

        _ref_tag = model.handleref.tag

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        return qset.select_related("ix", "ix__org"), {}

    def get_ix(self, inst):
        return self.sub_serializer(InternetExchangeSerializer, inst.ix)

    def to_representation(self, instance):
        data = super().to_representation(instance)

        if isinstance(data, dict):
            if (
                    "ixf_ixp_member_list_url" in data
                    and "ixf_ixp_member_list_url_visible" not in data
            ):
                # only `ixf_ixp_member_list_url` is present in the data
                # we need to add the `ixf_ixp_member_list_url_visible` field as
                # that is used to determine if the URL is visible to users during
                # the final, permission aware serialization
                try:
                    data["ixf_ixp_member_list_url_visible"] = getattr(
                        instance, "ixf_ixp_member_list_url_visible"
                    )
                except AttributeError:
                    pass
        return data


class InternetExchangeSerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.InternetExchange

    Possible relationship queries:
      - org_id, handled by serializer
      - fac_id, handled by prepare_query
      - net_id, handled by prepare_query
      - ixfac_id, handled by prepare_query
      - ixlan_id, handled by prepare_query
    """

    org_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), source="org"
    )

    org = serializers.SerializerMethodField()

    ixlan_set = nested(
        IXLanSerializer, exclude=["ix_id", "ix"], source="ixlan_set_active_prefetched"
    )
    fac_set = nested(
        FacilitySerializer,
        source="ixfac_set_active_prefetched",
        through="ixfac_set",
        getter="facility",
    )

    # suggest = serializers.BooleanField(required=False, write_only=True)

    ixf_net_count = serializers.IntegerField(read_only=True)
    ixf_last_import = RemoveMillisecondsDateTimeField(read_only=True)

    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    social_media = SocialMediaSerializer(required=False, many=True)
    tech_email = serializers.EmailField(required=True)

    tech_phone = serializers.CharField(required=False, allow_blank=True, default="")
    policy_phone = serializers.CharField(required=False, allow_blank=True, default="")

    sales_phone = serializers.CharField(required=False, allow_blank=True, default="")
    sales_email = serializers.CharField(required=False, allow_blank=True, default="")

    proto_unicast = serializers.SerializerMethodField()
    proto_ipv6 = serializers.SerializerMethodField()

    media = serializers.SerializerMethodField()

    status_dashboard = serializers.URLField(
        required=False, allow_null=True, allow_blank=True, default=""
    )

    class Meta:
        model = InternetExchange
        fields = [
                     "id",
                     "org_id",
                     "org",
                     "name",
                     "aka",
                     "name_long",
                     "city",
                     "country",
                     "region_continent",
                     "media",
                     "notes",
                     "proto_unicast",
                     "proto_multicast",
                     "proto_ipv6",
                     "website",
                     "social_media",
                     "url_stats",
                     "tech_email",
                     "tech_phone",
                     "policy_email",
                     "policy_phone",
                     "sales_phone",
                     "sales_email",
                     "fac_set",
                     "ixlan_set",
                     "ixf_net_count",
                     "ixf_last_import",
                     "service_level",
                     "terms",
                     "status_dashboard",
                 ] + HandleRefSerializer.Meta.fields
        _ref_tag = model.handleref.tag
        related_fields = ["org", "fac_set", "ixlan_set"]
        list_exclude = ["org"]

        read_only_fields = ["proto_multicast", "media", "logo"]

    def get_media(self, inst):
        # as per #1555 this should always return "Ethernet" as the field
        # is now deprecated
        return "Ethernet"

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        qset = qset.select_related("org")

        filters = get_relation_filters(
            [
                "ixlan_id",
                "ixlan",
                "ixfac_id",
                "ixfac",
                "fac_id",
                "fac",
                "net_id",
                "net",
                "net_count",
                "fac_count",
                "capacity",
            ],
            cls,
            **kwargs,
        )

        for field, e in list(filters.items()):
            for valid in ["ixlan", "ixfac", "fac", "net"]:
                if validate_relation_filter_field(field, valid):
                    fn = getattr(cls.Meta.model, f"related_to_{valid}")
                    qset = fn(qset=qset, field=field, **e)
                    break

            if field == "network_count":
                if e["filt"]:
                    flt = {f"net_count__{e['filt']}": e["value"]}
                else:
                    flt = {"net_count": e["value"]}
                qset = qset.filter(**flt)

            if field == "facility_count":
                if e["filt"]:
                    flt = {f"fac_count__{e['filt']}": e["value"]}
                else:
                    flt = {"fac_count": e["value"]}
                qset = qset.filter(**flt)

            if field == "capacity":
                qset = cls.Meta.model.filter_capacity(qset=qset, **e)

        if "ipblock" in kwargs:
            qset = cls.Meta.model.related_to_ipblock(
                kwargs.get("ipblock", [""])[0], qset=qset
            )
            filters.update({"ipblock": kwargs.get("ipblock")})

        if "asn_overlap" in kwargs:
            asns = kwargs.get("asn_overlap", [""])[0].split(",")
            qset = cls.Meta.model.overlapping_asns(asns, qset=qset)
            filters.update({"asn_overlap": kwargs.get("asn_overlap")})

        if "all_net" in kwargs:
            network_id_list = [
                int(net_id) for net_id in kwargs.get("all_net")[0].split(",")
            ]
            qset = cls.Meta.model.related_to_multiple_networks(
                value_list=network_id_list, qset=qset
            )
            filters.update({"all_net": kwargs.get("all_net")})

        if "not_net" in kwargs:
            networks = kwargs.get("not_net")[0].split(",")
            qset = cls.Meta.model.not_related_to_net(
                filt="in", value=networks, qset=qset
            )
            filters.update({"not_net": kwargs.get("not_net")})

        if "org_present" in kwargs:
            org_list = kwargs.get("org_present")[0].split(",")
            ix_ids = []

            # relation through netixlan
            ix_ids.extend(
                [
                    netixlan.ixlan_id
                    for netixlan in NetworkIXLan.objects.filter(
                    network__org_id__in=org_list
                )
                ]
            )

            # relation through ixfac
            ix_ids.extend(
                [
                    ixfac.ix_id
                    for ixfac in InternetExchangeFacility.objects.filter(
                    facility__org_id__in=org_list
                )
                ]
            )

            qset = qset.filter(id__in=set(ix_ids))

            filters.update({"org_present": kwargs.get("org_present")[0]})

        if "org_not_present" in kwargs:
            org_list = kwargs.get("org_not_present")[0].split(",")
            ix_ids = []

            # relation through netixlan
            ix_ids.extend(
                [
                    netixlan.ixlan_id
                    for netixlan in NetworkIXLan.objects.filter(
                    network__org_id__in=org_list
                )
                ]
            )

            # relation through ixfac
            ix_ids.extend(
                [
                    ixfac.ix_id
                    for ixfac in InternetExchangeFacility.objects.filter(
                    facility__org_id__in=org_list
                )
                ]
            )

            qset = qset.exclude(id__in=set(ix_ids))

            filters.update({"org_not_present": kwargs.get("org_not_present")[0]})

        return qset, filters

    def to_representation(self, data):
        # When an ix is created we want to add the ixlan_id and ixpfx_id
        # that were created to the representation (see #609)

        representation = super().to_representation(data)
        request = self.context.get("request")
        if request and request.method == "POST" and self.instance:
            ixlan = self.instance.ixlan
            ixpfx = ixlan.ixpfx_set.first()
            representation.update(ixlan_id=ixlan.id, ixpfx_id=ixpfx.id)

        if isinstance(representation, dict) and not representation.get("website"):
            representation["website"] = data.org.website

        return representation

    def get_org(self, inst):
        return self.sub_serializer(OrganizationSerializer, inst.org)

    def get_proto_ipv6(self, inst):
        return self.ixp_lan_active(inst).filter(protocol="IPv6").exists()

    def get_proto_unicast(self, inst):
        return self.ixp_lan_active(inst).filter(protocol="IPv4").exists()

    def ixp_lan_active(self, inst):
        return inst.ixlan_set.first().ixpfx_set(manager="handleref").filter(status="ok")


class CampusSerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.Campus
    """

    fac_set = nested(
        FacilitySerializer,
        exclude=["org_id", "org"],
        source="fac_set_active_prefetched",
    )
    org_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(), source="org"
    )
    org_name = serializers.CharField(source="org.name", read_only=True)
    org = serializers.SerializerMethodField()
    social_media = SocialMediaSerializer(required=False, many=True)

    class Meta:
        model = Campus
        depth = 0
        fields = [
                     "id",
                     "org_id",
                     "org_name",
                     "org",
                     "status",
                     "created",
                     "updated",
                     "name",
                     "name_long",
                     "notes",
                     "aka",
                     "website",
                     "social_media",
                     "fac_set",
                 ] + HandleRefSerializer.Meta.fields
        related_fields = ["fac_set", "org"]
        list_exclude = ["org"]
        read_only_fields = ["logo"]

        _ref_tag = model.handleref.tag

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        """
        Allows filtering by indirect relationships.

        Currently supports: facility
        """
        qset = qset.select_related("org")

        filters = get_relation_filters(["facility"], cls, **kwargs)

        for field, e in list(filters.items()):
            field = field.replace("facility", "fac_set")
            fn = getattr(cls.Meta.model, "related_to_facility")
            qset = fn(field=field, qset=qset, **e)

        return qset, filters

    def get_org(self, inst):
        return self.sub_serializer(OrganizationSerializer, inst.org)

    def to_representation(self, data):
        representation = super().to_representation(data)

        if isinstance(representation, dict) and not representation.get("website"):
            representation["website"] = data.org.website

        return representation


class OrganizationSerializer(ModelSerializer):
    """
    Serializer for peeringdb_server.models.Organization
    """

    net_set = nested(
        NetworkSerializer, exclude=["org_id", "org"], source="net_set_active_prefetched"
    )

    fac_set = nested(
        FacilitySerializer,
        exclude=["org_id", "org"],
        source="fac_set_active_prefetched",
    )

    ix_set = nested(
        InternetExchangeSerializer,
        exclude=["org_id", "org"],
        source="ix_set_active_prefetched",
    )

    carrier_set = nested(
        CarrierSerializer,
        exclude=["org_id", "org"],
        source="carrier_set_active_prefetched",
    )

    campus_set = nested(
        CampusSerializer,
        exclude=["org_id", "org"],
        source="campus_set_active_prefetched",
    )

    latitude = serializers.FloatField(read_only=True)
    longitude = serializers.FloatField(read_only=True)
    social_media = SocialMediaSerializer(required=False, many=True)

    class Meta:  # (AddressSerializer.Meta):
        model = Organization
        depth = 1
        fields = (
                [
                    "id",
                    "name",
                    "aka",
                    "name_long",
                    "website",
                    "social_media",
                    "notes",
                    "net_set",
                    "fac_set",
                    "ix_set",
                    "carrier_set",
                    "campus_set",
                ]
                + AddressSerializer.Meta.fields
                + HandleRefSerializer.Meta.fields
        )
        related_fields = [
            "fac_set",
            "net_set",
            "ix_set",
            "carrier_set",
            "campus_set",
        ]
        read_only_fields = ["logo"]
        _ref_tag = model.handleref.tag

    @classmethod
    def prepare_query(cls, qset, **kwargs):
        """
        Add special filter options

        Currently supports:

        - asn: filter by network asn
        """
        filters = {}

        if "asn" in kwargs:
            asn = kwargs.get("asn", [""])[0]
            qset = qset.filter(net_set__asn=asn, net_set__status="ok")
            filters.update({"asn": kwargs.get("asn")})

        return qset, filters


def validate_asset_lookup(ref_tag, ref_id, asset_type):
    """
    Validate asset lookup parameters and return the entity.

    Args:
        ref_tag: Entity type (org, fac, net, ix, carrier, campus)
        ref_id: Entity ID
        asset_type: Asset type (currently only 'logo')

    Returns:
        Entity instance if validation passes

    Raises:
        RestValidationError: If validation fails
    """
    if asset_type != "logo":
        raise RestValidationError(
            {
                "asset_type": f"Invalid asset_type: {asset_type}. Only 'logo' is supported"
            }
        )

    entity_model = ASSET_REFTAG_MAP.get(ref_tag)
    if not entity_model:
        raise RestValidationError(
            {
                "ref_tag": f"Invalid ref_tag: {ref_tag}. Must be one of: {', '.join(ASSET_REFTAG_MAP.keys())}"
            }
        )

    try:
        entity = entity_model.objects.get(id=ref_id, status="ok")
    except entity_model.DoesNotExist:
        raise RestValidationError(
            {"ref_id": f"{entity_model.__name__} with id {ref_id} not found"}
        )

    return entity


class AssetLookupSerializer(serializers.Serializer):
    """
    Base serializer for validating asset lookup parameters.
    Used by retrieve operations.
    """

    ref_tag = serializers.ChoiceField(
        choices=["org", "fac", "net", "ix", "carrier", "campus"],
        required=True,
        help_text="Entity type: org, fac, net, ix, carrier, or campus",
    )
    ref_id = serializers.IntegerField(
        required=True, help_text="ID of the entity to associate the asset with"
    )
    asset_type = serializers.ChoiceField(
        choices=["logo"],
        default="logo",
        help_text="Type of asset (currently only 'logo' is supported)",
    )

    def validate(self, data):
        """Validate entity reference"""
        ref_tag = data.get("ref_tag")
        ref_id = data.get("ref_id")
        asset_type = data.get("asset_type", "logo")

        entity = validate_asset_lookup(ref_tag, ref_id, asset_type)
        data["_entity"] = entity

        return data


REFTAG_MAP = {
    cls.Meta.model.handleref.tag: cls
    for cls in [
        OrganizationSerializer,
        NetworkSerializer,
        FacilitySerializer,
        InternetExchangeSerializer,
        InternetExchangeFacilitySerializer,
        NetworkFacilitySerializer,
        NetworkIXLanSerializer,
        NetworkContactSerializer,
        IXLanSerializer,
        IXLanPrefixSerializer,
        CarrierSerializer,
        CarrierFacilitySerializer,
        CampusSerializer,
    ]
}
