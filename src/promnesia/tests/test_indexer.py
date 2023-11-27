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
    # ugh. we modify the config very fast during tests
    # and pycache distinguishes identical filenames based on int mtime in seconds
    # so best to use different names to prevent undesired caching
    # https://github.com/python/cpython/blob/fb202af4470d6051a69bb9d2f44d7e8a1c99eb4f/Lib/importlib/_bootstrap_external.py#L714-L739
    # TODO could probably get rid of that if we switch from importlib config loading to exec()?
    config_count = 0

    def write_config(output: Path, gen) -> Path:
        nonlocal config_count
        cfg_path = output / f'config{config_count}.py'
        config_count += 1
        cfg_src = dedent('\n'.join(inspect.getsource(gen).splitlines()[1:])) + f"\nOUTPUT_DIR = r'{output}'"
        cfg_path.write_text(cfg_src)
        return cfg_path

    def cfg1() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [
            Source(demo.index, count=10, base_dt='2000-01-01', delta=30, name='demo1'),
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
