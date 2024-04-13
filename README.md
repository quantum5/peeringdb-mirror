# PeeringDB Mirror

This repository implements a simple, Django-based PeeringDB mirroring service
based on `django-peeringdb` and `peeringdb-py`.

Currently, this doesn't have full PeeringDB API compatibility, but there is a
sufficiently strong foundation to make that dream easily achievable through a
bit of Django metaprogramming. PRs welcome!

## Installation

1. Clone this repository: `git clone https://github.com/quantum5/peeringdb-mirror.git`;
2. Enter the cloned repo: `cd peeringdb-mirror`;
3. Create a virtualenv: `python3 -m venv venv`;
4. Activate the virtualenv for all subsequent commands: `. venv/bin/activate`;
5. Install dependencies: `pip install -r requirements.txt`;
6. Configure Django: `cp peeringdb_mirror/settings/{template,local}.py` and edit
   `peeringdb_mirror/settings/local.py`. You should change `SECRET_KEY` and
   update `DATABASES`. See the linked Django documentation for details;
7. Migrate database: `python manage.py migrate`;
8. Run initial database sync from PeeringDB: `python manage.py sync_peeringdb`;
   and
9. Run the WSGI app `peeringdb_mirror.wsgi:application` with your favourite
   WSGI-capable application server; and
10. Set up a cron job to run the `sync_peeringdb` command every hour:
    `0 * * * * /path/to/venv/bin/python /path/to/repo/manage.py sync_peeringdb`.

## Example uWSGI configuration in production

If you choose to run uWSGI, you can use the following configuration provided
for your convenience:

```ini
[uwsgi]
uid = peeringdb
gid = peeringdb
protocol = uwsgi
; For TCP socket
socket = :1234
; For Unix socket, you can do
; socket = /tmp/peeringdb-mirror.sock
master = true
pythonpath = /path/to/peeringdb-mirror
module = peeringdb_mirror.wsgi:application
buffer-size = 8192
die-on-term = true
workers = 3
threads = 4
```

Save this as `peeringdb.ini`. You can install `uwsgi` in the virtualenv by doing
`pip install uwsgi` and run it with the following `systemd` unit:

```ini
[Unit]
Description=PeeringDB mirror

[Service]
Type=simple
ExecStart=/path/to/peeringdb-mirror/venv/bin/uwsgi /path/to/peeringdb.ini

[Install]
WantedBy=multi-user.target
```
