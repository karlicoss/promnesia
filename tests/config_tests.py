import pytest
from more_itertools import ilen
from typing import Union, Iterable, List

from promnesia.common import Source

from common import throw


def test_minimal() -> None:
    '''
    Example of a smallest possible config, using a 'demo' source
    '''
    # import directly from promnesia, not promnesia.common
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


def test_sources_style() -> None:
    '''
    Testing 'styles' of specifying sources
    '''
    cfg = make('''
from promnesia.common import Source
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

    # just in case, test lambdas
    # with list
    lambda: list(demo.index()),

    # with generator
    lambda: iter(list(demo.index())),

    # example of lazy source
    # useful when arguments are somehow computed dynamically in config
    Source(lambda: demo.index(count=10), name='lazy'),
]
    ''')

    srcs = [s if isinstance(s, Source) else throw(s) for s in cfg.sources]

    [s1, s2, s3, s4, s5, s55, s6, s7, s77, s777] = srcs

    assert s1.name == 'explicit name'
    assert s2.name == 'another name'
    assert s3.name == 'demo'
    assert s4.name == 'demo'
    assert s5.name == 'demo'
    assert s55.name == 'demo'
    assert s6.name == 'demo'

    # can't say 'cfg' as name is intended here but anyway
    assert s7.name  == 'cfg'
    assert s77.name == 'cfg'
    assert s777.name == 'lazy'

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
from promnesia.common import Visit, Source, Loc

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
    [s1, s2, s3] = [s if isinstance(s, Source) else throw(s) for s in cfg.sources]

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
from promnesia.common import Source

def lazy():
    from promnesia.sources import demo
    print("Hello, I'm so lazy...")
    yield from demo.index()

SOURCES = [
    lazy,
]
    ''')
    srcs = [s if isinstance(s, Source) else throw(s) for s in cfg.sources]
    [s] = srcs

    assert s.name == 'cfg' # TODO this should be fixed... but not a big deal

    index(cfg)

# TODO later
# or like that:
# (i for i in lazy()),

# TODO later, support stuff that returns sources lazily? e.g. lambda: Source(...)
# not sure if it's very useful


def test_sources_errors() -> None:
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
from promnesia.common import Source
from promnesia.sources import demo
INDEXERS = [
    Source(demo.index, src='legacy name'),
]
    ''')

    [s1] = cfg.sources
    assert isinstance(s1, Source)

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


from contextlib import contextmanager
@contextmanager
def with_config(cfg: Union[str, Config]):
    import promnesia.config as C
    assert not C.has()
    cfg2: Config = make(cfg) if isinstance(cfg, str) else cfg
    try:
        C.instance = cfg2
        assert C.has()
        yield
    finally:
        C.reset()


def index(cfg: Union[str, Config], check=True) -> List[Exception]:
    from promnesia.__main__ import _do_index
    with with_config(cfg):
        errors = list(_do_index())
        if check:
            assert len(errors) == 0, errors
        # visits = cfg.output_dir / 'promnesia.sqlite'
        # TODO query visit count too
        return errors
