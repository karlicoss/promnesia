from pathlib import Path
from typing import List, Optional
import importlib.util

from typing_extensions import Protocol
import pytz

from kython.ktyping import PathIsh


class Config(Protocol):
    FALLBACK_TIMEZONE: pytz.BaseTzInfo
    CACHE_DIR: PathIsh # TODO do not use cache if it's none?
    OUTPUT_DIR: PathIsh
    INDEXERS: List
    FILTERS: List[str]


instance: Optional[Config] = None


def get() -> Config:
    assert instance is not None
    return instance


def load_from(config_file: Path) -> None:
    global instance
    assert instance is None
    instance = import_config(config_file)


def reset() -> None:
    global instance
    assert instance is not None
    instance = None


def import_config(config_file: PathIsh) -> Config:
    p = Path(config_file)
    name = p.stem
    spec = importlib.util.spec_from_file_location(name, p) # type: ignore
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod) # type: ignore
    return mod # type: ignore
