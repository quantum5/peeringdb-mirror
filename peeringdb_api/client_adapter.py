from django_peeringdb.client_adaptor import backend


def load_backend(**kwargs):
    return backend
