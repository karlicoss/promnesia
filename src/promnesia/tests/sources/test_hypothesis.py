from pathlib import Path

from my.core.cfg import tmp_config

from ...__main__ import do_index
from ...database.load import get_all_db_visits
from ..common import get_testdata, write_config


def index_hypothesis(tmp_path: Path) -> None:
    def cfg() -> None:
        from promnesia.common import Source
        from promnesia.sources import hypothesis

        SOURCES = [Source(hypothesis.index, name='hyp')]  # noqa: F841

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)

    class hpi_config:
        class hypothesis:
            export_path = get_testdata('hypexport/testdata') / 'netrights-dashboard-mockup/data/*.json'

    with tmp_config(modules='my.hypothesis', config=hpi_config):
        do_index(cfg_path)


def test_hypothesis(tmp_path: Path) -> None:
    index_hypothesis(tmp_path)

    visits = get_all_db_visits(tmp_path / 'promnesia.sqlite')
    assert len(visits) > 100

    [vis] = [x for x in visits if 'fundamental fact of evolution' in (x.context or '')]

    assert vis.norm_url == 'wired.com/2017/04/the-myth-of-a-superhuman-ai'
    assert vis.orig_url == 'https://www.wired.com/2017/04/the-myth-of-a-superhuman-ai/'
    assert (
        vis.locator.href == 'https://hyp.is/_Z9ccmVZEeexBOO7mToqdg/www.wired.com/2017/04/the-myth-of-a-superhuman-ai/'
    )
    assert 'misconception about evolution is fueling misconception about AI' in (
        vis.context or ''
    )  # contains notes as well
