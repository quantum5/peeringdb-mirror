from django.urls import path

from peeringdb_ui.views.facility import view_facility
from peeringdb_ui.views.ix import view_exchange
from peeringdb_ui.views.network import view_network

urlpatterns = [
    path("net/<int:pk>/", view_network, name="net-view"),
    path("ix/<int:pk>/", view_exchange, name="ix-view"),
    path("fac/<int:pk>/", view_facility, name="fac-view"),
]
