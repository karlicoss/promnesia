import pytest # type: ignore
from more_itertools import ilen

from promnesia import Source


def test_minimal():
    '''
    Example of a smallest possible config, using a 'demo' source
    '''
    cfg = make('''
from promnesia import Source
from promnesia.sources import demo

SOURCES = [
    Source(demo.index),
]
''')
    assert ilen(cfg.sources) == 1
    assert all(isinstance(s, Source) for s in cfg.sources)
    # todo output dirs?
    index(cfg)


def test_sources_style():
    '''
    Testing 'styles' of specifying sources
    '''
    cfg = make('''
from promnesia import Source
from promnesia.sources import demo

SOURCES = [
    # you can pass arguments to index functions
    Source(demo.index, count=10, name='explicit name'),

    # or rely on the default argument!
    Source(demo.index, name='another name'),

    # or rely on default source name name (will be guessed as 'demo')
    Source(demo.index),

    # rely on default index function
    Source(demo),

    # no need for Source() either!
    demo.index,
    demo,

    # I guess this is as simple as it possibly gets...
    'promnesia.sources.demo',
]
    ''')

    srcs = cfg.sources
    assert all(isinstance(_, Source) for _ in cfg.sources)

    [s1, s2, s3, s4, s5, s55, s6] = srcs

    assert s1.name == 'explicit name'
    assert s2.name == 'another name'
    assert s3.name == 'demo'
    assert s4.name == 'demo'
    assert s5.name == 'demo'
    assert s55.name == 'demo'
    assert s6.name == 'demo'

    index(cfg)
    # TODO assert on results count?


# TODO ugh. allow not to have locator
# ideally you can construct a visit with a link and that's it
def test_sources_style_more():
    '''
    Now, sources are not magic -- they are just functions emitting visits
    '''
    cfg = make('''
from typing import Iterable
from promnesia import Visit, Source, Loc

def my_indexer() -> Iterable[Visit]:
    from datetime import datetime
    for link in ['reddit.com', 'beepb00p.xyz']:
        yield Visit(
            url=link,
            dt=datetime.min,
            locator=Loc.make('test'),
        )

SOURCES = [
    # you can just pass the function name here
    my_indexer,

    # or give it an explicit name (instead of a guess)
    Source(my_indexer, name='nice name'),
]


class MyIndexer:
    def index():
        from promnesia.sources import demo
        return list(demo.index())

SOURCES.append(
    MyIndexer,
)

''')
    srcs = cfg.sources
    [s1, s2, s3] = srcs

    assert s1.name == 'cfg' # TODO would be nice to guess 'my_indexer' instead...
    assert s2.name == 'nice name'
    assert s3.name == 'cfg' # TODO fix it, make MyIndexer?

    index(cfg)


def test_sources_lazy():
    '''
    Demonstration of ways to return 'lazy' and generally more advanced sources

    Lazy sources could be useful to do some conditional magic or make more defensive against imports, excra configuration. You'll know when you need it ;)
    '''

    cfg = make('''
from promnesia import Source

def lazy():
    from promnesia.sources import demo
    print("Hello, I'm so lazy...")
    yield from demo.index()

SOURCES = [
    lazy,
]
    ''')
    srcs = cfg.sources
    assert all(isinstance(_, Source) for _ in cfg.sources)
    [s] = srcs

    assert s.name == 'cfg' # TODO this should be fixed... but not a big deal

    index(cfg)

# TODO later
# or like that:
# (i for i in lazy()),

# TODO later, support stuff that returns sources lazily? e.g. lambda: Source(...)
# not sure if it's very useful


def test_sources_errors():
    '''
    Testing defensiveness of config against various errors
    '''
    cfg = make('''
SOURCES = [
    'non.existing.module',

    lambda: bad.attribute,

    'promnesia.sources.demo',
]
    ''')

    # nothing fails so far! It's defensive!
    srcs = list(cfg.sources)

    [e1, s1, s2] = srcs

    assert isinstance(e1, Exception)
    assert isinstance(s1, Source)
    assert isinstance(s2, Source)

    errors = index(cfg, check=False)
    assert len(errors) == 2 # errors simply propagate
  


def test_no_sources():
    cfg = make('''
''')
    # raises because no SOURCES
    with pytest.raises(RuntimeError):
        list(cfg.sources)


def test_empty_sources():
    cfg = make('''
SOURCES = []
    ''')
    # raises because empty SOURCES
    with pytest.raises(RuntimeError):
        list(cfg.sources)



def test_legacy():
    cfg = make('''
from promnesia import Source
from promnesia.sources import demo
INDEXERS = [
    Source(demo.index, src='legacy name'),
]
    ''')

    [s1] = cfg.sources

    assert s1.name == 'legacy name'

    index(cfg)


from pathlib import Path
from tempfile import TemporaryDirectory

from promnesia.config import import_config, Config


def make(body: str) -> Config:
    with TemporaryDirectory() as td:
        tdir = Path(td)
        cp = tdir / 'cfg.py'
        cp.write_text(body)
        return import_config(cp)


def index(cfg: Config, check=True):
    import promnesia.config as config
    from promnesia.__main__ import _do_index
    config.instance = cfg
    try:
        errors = list(_do_index())
        if check:
            assert len(errors) == 0, errors
        # visits = cfg.output_dir / 'promnesia.sqlite'
        # TODO query visit count too
        return errors
    finally:
        config.reset()
