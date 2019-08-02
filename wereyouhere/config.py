from pathlib import Path
from typing import List, Optional

from typing_extensions import Protocol
import pytz

from kython.ktyping import PathIsh


class Config(Protocol):
    FALLBACK_TIMEZONE: pytz.BaseTzInfo
    OUTPUT_DIR: PathIsh
    EXTRACTORS: List
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
    mpath = Path(config_file)
    import os, sys, importlib
    sys.path.append(str(mpath.parent))
    try:
        res = importlib.import_module(mpath.stem)
        # TODO hmm. check that config conforms to the protocol?? perhaps even in config itself?
        return res # type: ignore
    finally:
        sys.path.pop()
