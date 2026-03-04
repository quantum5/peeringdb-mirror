from django.urls import path

from peeringdb_ui.views.carrier import view_carrier
from peeringdb_ui.views.facility import view_facility
from peeringdb_ui.views.index import view_index
from peeringdb_ui.views.ix import view_exchange
from peeringdb_ui.views.network import view_network
from peeringdb_ui.views.search import request_search

urlpatterns = [
    path('', view_index, name='home'),
    path('search', request_search),
    path('net/<int:pk>', view_network, name='net-view'),
    path('ix/<int:pk>', view_exchange, name='ix-view'),
    path('fac/<int:pk>', view_facility, name='fac-view'),
    path('carrier/<int:pk>', view_carrier, name='carrier-view'),
]
