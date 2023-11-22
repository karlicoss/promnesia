from pathlib import Path
from subprocess import check_call

from .common import promnesia_bin
from .server_helper import run_server


def test_status_error() -> None:
    """
    If DB doesn't exist, server should handle it gracefully and respond with error
    """
    with run_server(db='/does/not/exist') as server:
        response = server.post('/status')

        # TODO ugh currently returns 200? maybe should return proper error, but need to handle in extension
        # assert response.status_code == 404

        body = response.json()

        version = body['version']
        assert version is not None
        assert len(version.split('.')) >= 2  # random check..

        assert 'ERROR' in body['db']  # defensive, it doesn't exist


def test_basic(tmp_path: Path) -> None:
    # TODO use tmp_path to index
    cfg = tmp_path / 'config.py'
    # TODO simplify this, make sure it can just use default demo provider
    cfg.write_text("""
from datetime import datetime, timedelta
from promnesia.common import Source
from promnesia.sources import demo
SOURCES = [Source(demo.index, base_dt=datetime(2000, 1, 1), delta=timedelta(minutes=30))]
    """)
    # TODO index directly here instead
    # FIXME need to make sure it works without --overwrite (by indexing into tmp path instead)
    check_call(promnesia_bin('index', '--config', cfg, '--overwrite'))

    # force timezone here, otherwise dependeing on the test env response varies
    with run_server(timezone='America/New_York') as server:
        r = server.post('/visits', json={'url': 'whatever'}).json()
        assert r['visits'] == []

        r = server.post('/visits', json={'url': 'https://demo.com/page0.html'})
        rj = r.json()
        assert rj['normalised_url'] == 'demo.com/page0.html'
        [v] = rj['visits']
        assert v['src'] == 'demo'
        assert v['locator']['title'] == 'demo'

        assert v['dt'] == '01 Jan 2000 00:00:00 -0500'
