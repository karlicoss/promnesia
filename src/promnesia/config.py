from pathlib import Path
from typing import List, Optional, Union, NamedTuple
import importlib.util
import warnings

import pytz

from .common import PathIsh, get_tmpdir


class Config(NamedTuple):
    OUTPUT_DIR: PathIsh
    # TODO remove default from sources once migrated
    SOURCES: List = []
    INDEXERS: List = []
    CACHE_DIR: Optional[PathIsh] = None
    FILTERS: List[str] = []

    @property
    def sources(self):
        if self.INDEXERS is not None:
            warnings.warn("'INDEXERS' is deprecated. Please use 'SOURCES'!", DeprecationWarning)

        res = self.SOURCES or self.INDEXERS
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

    @property
    def output_dir(self) -> Path:
        return Path(self.OUTPUT_DIR)


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
