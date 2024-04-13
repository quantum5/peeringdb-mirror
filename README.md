# PeeringDB Mirror

This repository implements a simple, Django-based PeeringDB mirroring service
based on `django-peeringdb` and `peeringdb-py`.

Currently, this doesn't have full PeeringDB API compatibility, but there is a
sufficiently strong foundation to make that dream easily achievable through a
bit of Django metaprogramming. PRs welcome!

## Installation

1. Clone this repository: `git clone https://github.com/quantum5/peeringdb-mirror.git`;
2. Create a virtualenv: `python3 -m venv venv`;
3. Install dependencies: `pip install -r requirements.txt`;
4. Configure Django: `cp peeringdb_mirror/settings/{template,local}.py` and edit
   `peeringdb_mirror/settings/local.py`. You should change `SECRET_KEY` and
   update `DATABASES`. See the linked Django documentation for details;
5. Migrate database: `python manage.py migrate`;
6. Run the WSGI app `peeringdb_mirror.wsgi:application` with your favourite
   WSGI-capable application server.
