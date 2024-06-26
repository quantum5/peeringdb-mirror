from django.urls import path
from django_peeringdb import models

from peeringdb_api.views import PeeringDBDetailView, PeeringDBListView

urlpatterns = [
    path('api/org', PeeringDBListView.as_view(model=models.Organization)),
    path('api/fac', PeeringDBListView.as_view(model=models.Facility)),
    path('api/net', PeeringDBListView.as_view(model=models.Network)),
    path('api/ix', PeeringDBListView.as_view(model=models.InternetExchange)),
    path('api/campus', PeeringDBListView.as_view(model=models.Campus)),
    path('api/carrier', PeeringDBListView.as_view(model=models.Carrier)),
    path('api/carrierfac', PeeringDBListView.as_view(model=models.CarrierFacility)),
    path('api/ixfac', PeeringDBListView.as_view(model=models.InternetExchangeFacility)),
    path('api/ixlan', PeeringDBListView.as_view(model=models.IXLan)),
    path('api/ixpfx', PeeringDBListView.as_view(model=models.IXLanPrefix)),
    path('api/netfac', PeeringDBListView.as_view(model=models.NetworkFacility)),
    path('api/netixlan', PeeringDBListView.as_view(model=models.NetworkIXLan)),
    path('api/poc', PeeringDBListView.as_view(model=models.NetworkContact)),

    path('api/org/<int:pk>', PeeringDBDetailView.as_view(model=models.Organization)),
    path('api/fac/<int:pk>', PeeringDBDetailView.as_view(model=models.Facility)),
    path('api/net/<int:pk>', PeeringDBDetailView.as_view(model=models.Network)),
    path('api/ix/<int:pk>', PeeringDBDetailView.as_view(model=models.InternetExchange)),
    path('api/campus/<int:pk>', PeeringDBDetailView.as_view(model=models.Campus)),
    path('api/carrier/<int:pk>', PeeringDBDetailView.as_view(model=models.Carrier)),
    path('api/carrierfac/<int:pk>', PeeringDBDetailView.as_view(model=models.CarrierFacility)),
    path('api/ixfac/<int:pk>', PeeringDBDetailView.as_view(model=models.InternetExchangeFacility)),
    path('api/ixlan/<int:pk>', PeeringDBDetailView.as_view(model=models.IXLan)),
    path('api/ixpfx/<int:pk>', PeeringDBDetailView.as_view(model=models.IXLanPrefix)),
    path('api/netfac/<int:pk>', PeeringDBDetailView.as_view(model=models.NetworkFacility)),
    path('api/netixlan/<int:pk>', PeeringDBDetailView.as_view(model=models.NetworkIXLan)),
    path('api/poc/<int:pk>', PeeringDBDetailView.as_view(model=models.NetworkContact)),
]
