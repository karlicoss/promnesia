from collections import Counter
import inspect
from pathlib import Path
from textwrap import dedent

import pytest

from ..__main__ import do_index
from ..database.load import get_all_db_visits


def get_stats(tmp_path: Path) -> Counter:
    visits = get_all_db_visits(tmp_path / 'promnesia.sqlite')
    return Counter(v.src for v in visits)


@pytest.mark.parametrize('mode', ['update', 'overwrite'])
def test_indexing_mode(tmp_path: Path, mode: str) -> None:
    def write_config(output: Path, gen) -> Path:
        cfg_path = output / 'config.py'
        cfg_src = dedent('\n'.join(inspect.getsource(gen).splitlines()[1:])) + f"\nOUTPUT_DIR = r'{output}'"
        cfg_path.write_text(cfg_src)
        return cfg_path

    def cfg1() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [
            Source(demo.index, count=10, base_dt='2000-01-01', delta=30, name='demo1'),
            # FIXME wtf -- if we remove the comment, the test isn't passing???
            # must be some weird sort of caching??
            Source(demo.index, count=20, base_dt='2001-01-01', delta=30, name='demo2'),
        ]

    cfg = write_config(tmp_path, cfg1)
    do_index(cfg)
    stats = get_stats(tmp_path)
    assert stats == {'demo1': 10, 'demo2': 20}

    def cfg2() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [
            Source(demo.index, count=30, base_dt='2005-01-01', delta=30, name='demo2'),
            Source(demo.index, count=40, base_dt='2010-01-01', delta=30, name='demo3'),
        ]

    cfg = write_config(tmp_path, cfg2)
    do_index(cfg, overwrite_db={'overwrite': True, 'update': False}[mode])
    # TODO use some sort of test helper?
    stats = get_stats(tmp_path)

    if mode == 'update':
        # should keep the original visits too!
        assert stats == {'demo1': 10, 'demo2': 30, 'demo3': 40}
    else:
        # should overwrite with newly indexed visits
        assert stats == {'demo2': 30, 'demo3': 40}
