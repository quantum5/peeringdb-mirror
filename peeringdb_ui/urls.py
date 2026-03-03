from django.urls import path

from peeringdb_ui.views.network import view_network

urlpatterns = [
    path("net/<int:id>/", view_network, name="net-view"),
]
