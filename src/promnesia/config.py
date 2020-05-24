from pathlib import Path
from typing import List, Optional, Union, NamedTuple
import importlib.util
import warnings

import pytz

from .common import PathIsh, get_tmpdir, appdirs


class Config(NamedTuple):
    # TODO remove default from sources once migrated
    SOURCES: List = []

    # if not specified, uses user data dir
    OUTPUT_DIR: Optional[PathIsh] = None

    CACHE_DIR: Optional[PathIsh] = None
    FILTERS: List[str] = []
    #
    # NOTE: INDEXERS is deprecated, use SOURCES instead
    INDEXERS: List = []

    @property
    def sources(self):
        if len(self.INDEXERS) > 0:
            warnings.warn("'INDEXERS' is deprecated. Please use 'SOURCES'!", DeprecationWarning)

        res = self.SOURCES + self.INDEXERS
        # TODO enable it?
        # assert len(res) > 0, "Expected some sources"
        return res

    @property
    def cache_dir(self) -> Path:
        cd = self.CACHE_DIR
        # TODO maybe do not use cache if it's none?
        assert cd is not None
        res = Path(cd)
        res.mkdir(exist_ok=True) # TODO not sure about parents=True
        return res

    # TODO make this optional, default to .cache or something?
    # TODO also tmp dir -- perhaps should be in cache or at least possible to specify in config? not sure if useful
    @property
    def output_dir(self) -> Path:
        odir = self.OUTPUT_DIR
        if odir is not None:
            return Path(odir)
        else:
            dirs = appdirs()
            return Path(dirs.user_data_dir)


instance: Optional[Config] = None


def has() -> bool:
    return instance is not None

def get() -> Config:
    assert instance is not None
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

    # TODO just exec??
    name = p.stem
    spec = importlib.util.spec_from_file_location(name, p) # type: ignore
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod) # type: ignore

    d = {}
    for f in Config._fields:
        if hasattr(mod, f):
            d[f] = getattr(mod, f)
    return Config(**d)
