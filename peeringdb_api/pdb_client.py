from django.conf import settings
from peeringdb import SUPPORTED_BACKENDS
from peeringdb.client import Client

SUPPORTED_BACKENDS['peeringdb_mirror_api'] = 'peeringdb_api.client_adapter'

client = Client({
    'orm': {
        'backend': 'peeringdb_mirror_api',
    },
    'sync': {
        'url': settings.PEERINGDB_API,
        'api_key': settings.PEERINGDB_API_KEY or '',
        'timeout': 0,
    }
})
