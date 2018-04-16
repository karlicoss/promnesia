from typing import NamedTuple, Set, Iterable, Dict, TypeVar, Callable

from datetime import datetime

Date = datetime
class Visit(NamedTuple):
    dt: datetime
    tag: str = None
    context: str = None

Url = str
class Entry(NamedTuple):
    url: Url
    visits: Set[Visit]
    # TODO compare urls?

class History:
    def __init__(self):
        self.urls: Dict[Url, Entry] = {}

    @classmethod
    def from_urls(cls, urls: Dict[Url, Entry]) -> 'History':
        hist = cls()
        hist.urls = urls
        return hist

    def filtered(self, url: Url) -> bool:
        SCHEMAS = ['chrome-extension://', 'chrome-error://']
        for s in SCHEMAS:
            if url.startswith(s):
                return True
        return False

    def register(self, url: Url, v: Visit) -> None:
        if self.filtered(url):
            return

        e = self.urls.get(url, None)
        if e is None:
            e = Entry(url=url, visits=set())
        e.visits.add(v)
        self.urls[url] = e

    def __len__(self) -> int:
        return len(self.urls)

    def items(self):
        return self.urls.items()

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
    return History.from_urls(merge_dicts(entry_merger, [h.urls for h in hists]))

