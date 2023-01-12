from pathlib import Path
import os
from types import ModuleType
from typing import List, Optional, Union, NamedTuple, Iterable, Callable
import importlib
import importlib.util
import warnings

from .common import PathIsh, get_tmpdir, appdirs, default_output_dir, default_cache_dir, user_config_file
from .common import Res, Source, DbVisit


HookT = Callable[[Res[DbVisit]], Iterable[Res[DbVisit]]]


from typing import Any


ModuleName = str

# something that can be converted into a proper Source
ConfigSource = Union[Source, ModuleName, ModuleType]


class Config(NamedTuple):
    # TODO remove default from sources once migrated
    SOURCES: List[ConfigSource] = []

    # if not specified, uses user data dir
    OUTPUT_DIR: Optional[PathIsh] = None

    CACHE_DIR: Optional[PathIsh] = ''
    FILTERS: List[str] = []

    HOOK: Optional[HookT] = None

    #
    # NOTE: INDEXERS is deprecated, use SOURCES instead
    INDEXERS: List[ConfigSource] = []
    #MIME_HANDLER: Optional[str] = None # TODO

    @property
    def sources(self) -> Iterable[Res[Source]]:
        idx = self.INDEXERS

        if len(self.INDEXERS) > 0:
            warnings.warn("'INDEXERS' is deprecated. Please use 'SOURCES'!", DeprecationWarning)

        raw = self.SOURCES + self.INDEXERS

        if len(raw) == 0:
            raise RuntimeError("Please specify SOURCES in the config! See https://github.com/karlicoss/promnesia#setup for more information")

        for r in raw:
            if isinstance(r, ModuleName):
                try:
                    r = importlib.import_module(r)
                except ModuleNotFoundError as e:
                    # todo better error reporting?
                    yield e
                    continue

            if isinstance(r, Source):
                yield r
            else:
                # otherwise Source object can take care of the module we passed
                # (see SourceIsh)
                yield Source(r)

    @property
    def cache_dir(self) -> Optional[Path]:
        cd = self.CACHE_DIR
        cpath: Optional[Path]
        if cd is None:
            cpath = None # means 'disabled' in cachew
        elif cd == '': # meh.. but need to make it None friendly..
            cpath = default_cache_dir()
        else:
            cpath = Path(cd)
        if cpath is not None:
            cpath.mkdir(exist_ok=True, parents=True)
        return cpath

    # TODO also tmp dir -- perhaps should be in cache or at least possible to specify in config? not sure if useful
    @property
    def output_dir(self) -> Path:
        odir = self.OUTPUT_DIR
        opath = default_output_dir() if odir is None else Path(odir)
        opath.mkdir(exist_ok=True, parents=True)
        return opath

    @property
    def db(self) -> Path:
        return self.output_dir / 'promnesia.sqlite'

    @property
    def hook(self) -> Optional[HookT]:
        return self.HOOK

instance: Optional[Config] = None


def has() -> bool:
    return instance is not None

def get() -> Config:
    assert instance is not None, "Expected config to be set, but it's not"
    return instance


def load_from(config_file: Path) -> None:
    global instance
    instance = import_config(config_file)


def reset() -> None:
    global instance
    assert instance is not None
    instance = None


def import_config(config_file: PathIsh) -> Config:
    p = Path(config_file)

    # todo just exec??
    name = p.stem
    spec = importlib.util.spec_from_file_location(name, p); assert spec is not None
    mod = importlib.util.module_from_spec(spec); assert mod is not None
    loader = spec.loader; assert loader is not None
    loader.exec_module(mod) # type: ignore[attr-defined]

    d = {}
    for f in Config._fields:
        if hasattr(mod, f):
            d[f] = getattr(mod, f)
    return Config(**d)


# TODO: ugh. this causes warnings to be repeated multiple times... need to reuse the pool or something..
def use_cores() -> Optional[int]:
    '''
    Somewhat experimental.
    For now only used in sources.auto, perhaps later will be shared among the other indexers.
    '''
    # most likely needs to be some sort of pipeline thing?
    cs = os.environ.get('PROMNESIA_CORES', None)
    if cs is None:
        return None
    try:
        return int(cs)
    except ValueError: # any other value means 'use all
        return 0


def extra_fd_args() -> List[str]:
    '''
    Not sure where it belongs yet... so via env variable for now
    Can be used to pass --ignore-file parameter
    '''
    v = os.environ.get('PROMNESIA_FD_EXTRA_ARGS', '')
    extra = v.split() # eh, hopefully splitting that way is ok...
    return extra
