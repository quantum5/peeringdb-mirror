from django.conf import settings
from django.core.management.base import BaseCommand
from peeringdb import resource

from peeringdb_api.pdb_client import client


class Command(BaseCommand):
    help = 'Syncs the PeeringDB database.'

    def handle(self, *args, **options):
        rs = resource.all_resources()
        client.updater.update_all(rs, fetch_private=bool(settings.PEERINGDB_API_KEY))
