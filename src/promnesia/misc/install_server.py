#!/usr/bin/env python3
import argparse

import os
from pathlib import Path
from subprocess import check_call, run

from .. import root
from .. import server

SYSTEMD_CONFIG = """
[Unit]
Description=Promnesia browser extension backend

[Install]
WantedBy=default.target

[Service]
ExecStart={launcher} {extra_args}
Type=simple
Restart=always
"""


def systemd(*args, method=check_call):
    method([
        'systemctl', '--no-pager', '--user', *args,
    ])


def install(args):
    unit_name = args.unit_name
    out = Path(f'~/.config/systemd/user/{unit_name}').expanduser()
    print(f"Writing systemd config to {out}:")

    # ugh. we want to know whether we're invoked 'properly' as an executable or ad-hoc via scripts/promnesia
    if os.environ.get('DIRTY_RUN') is not None:
        launcher = str(root() / 'scripts/promnesia')
    else:
        # must be installed, so available in PATH
        import distutils.spawn
        exe = distutils.spawn.find_executable('promnesia'); assert exe is not None
        launcher = exe # older systemd wants absolute paths..

    extra_args = f'serve --db {args.db} --timezone {args.timezone} --port {args.port}'

    out.parent.mkdir(parents=True, exist_ok=True) # sometimes systemd dir doesn't exist
    out.write_text(SYSTEMD_CONFIG.format(
        launcher=launcher,
        extra_args=extra_args,
    ))

    try:
        systemd('stop' , unit_name, method=run) # ignore errors here if it wasn't running in the first place
        systemd('daemon-reload')
        systemd('enable', unit_name)
        systemd('start' , unit_name)
        systemd('status', unit_name)
    except Exception as e:
        print(f"Something has gone wrong... you might want to use 'journalctl --user -u {unit_name}' to investigate")
        raise e


def setup_parser(p: argparse.ArgumentParser):
    p.add_argument('--unit-name', type=str, default='promnesia.service', help='Systemd unit name')
    server.setup_parser(p)
