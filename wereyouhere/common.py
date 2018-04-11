from typing import NamedTuple, Set, Iterable, Dict, TypeVar, Callable

from datetime import datetime

Date = datetime
class Visit(NamedTuple):
    dt: datetime
    tag: str = ""

Url = str
class Entry(NamedTuple):
    url: Url
    visits: Set[Visit]
    # TODO compare urls?

# mm, doesn't make much sense to duplicate url...
History = Dict[Url, Entry]

# f is value merger function
_K = TypeVar("_K")
_V = TypeVar("_V")

def merge_dicts(f: Callable[[_V, _V], _V], dicts: Iterable[Dict[_K, _V]]):
    res: Dict[_K, _V] = {}
    for d in dicts:
        for k, v in d.items():
            if k not in res:
                res[k] = v
            else:
                res[k] = f(res[k], v)
    return res

def entry_merger(a: Entry, b: Entry):
    a.visits.update(b.visits)
    return a

def merge_histories(hists: Iterable[History]) -> History:
    return merge_dicts(entry_merger, hists)

