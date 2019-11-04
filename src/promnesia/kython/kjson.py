"""
Some experimental ideas on JSON processing.
This is a bit overengineered and I admit it!
I'll make it more readable, but in the meantime feel free to open an issue if you're confused about something.
"""

from typing import Any, Dict, List, Union, Tuple, cast


JDict = Dict[str, Any] # TODO not sure if we can do recursive..
JList = List[Any]
JPrim = Union[str, int, float] # , type(None)]

Json = Union[JDict, JList, JPrim]

JPathPart = Tuple[Json, Union[str, int]]

JPath = Tuple[JPathPart, ...]


class JsonProcessor:
    SKIP = object()

    def handle_dict(self, js: JDict, jp: JPath) -> Any:
        pass

    def handle_list(self, js: JList, jp: JPath) -> Any:
        pass

    def handle_str(self, js: str, jp: JPath) -> Any:
        pass

    def do_dict(self, js: JDict, jp: JPath) -> None:
        # pylint: disable=assignment-from-no-return
        res = self.handle_dict(js, jp)
        if res is self.SKIP:
            return
        for k, v in js.items():
            path = cast(JPath, jp + ((js, k), ))
            self._do(v, path)

    def do_list(self, js: JList, jp: JPath) -> None:
        # pylint: disable=assignment-from-no-return
        res = self.handle_list(js, jp)
        if res is self.SKIP:
            return
        for i, x in enumerate(js):
            path = cast(JPath, jp + ((js, i), ))
            self._do(x, path)

    def _do(self, js: Json, path: JPath) -> None:
        if isinstance(js, dict): # TODO have functions for dict like, list like etc
            self.do_dict(js, path)
        elif isinstance(js, list):
            self.do_list(js, path)
        elif isinstance(js, str):
            self.handle_str(js, path)
        elif isinstance(js, (int, bool, float, type(None))):
            pass # TODO process that as well
        else:
            raise RuntimeError(f'unexpected item {js} of type {type(js)}')

    def run(self, js: Json) -> None:
        path = cast(JPath, ())
        self._do(js, path)

    @classmethod
    def kpath(cls, path: JPath) -> Tuple[JPathPart, ...]:
        return tuple(x[1] for x in path) # type: ignore

# TODO path is a sequence of jsons and keys?

def test_json_processor():
    handled = []
    class Proc(JsonProcessor):
        def handle_dict(self, value: JDict, path):
            if 'skipme' in self.kpath(path):
                return JsonProcessor.SKIP

        def handle_str(self, value: str, path):
            if 'http' in value:
                handled.append((value, path))

    j = {
        'skipme': {
            'x': {
                'y': [
                    123,
                    {
                        'description': 'whatever',
                        'link': 'http://ya.ru',
                    },
                ]
            }
        },
        'a': [1, 2, 3],
        'x': {
            'y': [
                123,
                {
                    'description': 'whatever',
                    'link': 'http://reddit.com',
                },
            ]
        },
    }

    p = Proc()
    p.run(j)
    assert len(handled) > 0

    [h1] = handled
    (link, path) = h1
    assert link == 'http://reddit.com'
    pp = [p[1] for p in path]
    assert pp == ['x', 'y', 1, 'link']


from datetime import datetime
# TODO don't really like it...
def _date2str(dt: datetime) -> str:
    return dt.isoformat()


import dateutil.parser
def _str2date(s: str) -> datetime:
    # yep, it looks like the easiest way to parse iso formatted date...
    return dateutil.parser.parse(s)


class ToFromJson:
    # TODO additional way to specify date fields?
    def __init__(self, cls, as_dates: List[str]) -> None:
        self.cls = cls
        self.dates = as_dates

    def to(self, obj):
        res = obj._asdict()
        for k in res:
            v = res[k]
            if k in self.dates:
                res[k] = _date2str(v)

        # make sure it's actually inverse
        inv = self.from_(res)
        assert obj == inv
        return res

    def from_(self, jj):
        res = {}
        for k in jj:
            v = jj[k]
            if k in self.dates:
                res[k] = _str2date(v)
            else:
                res[k] = v
        return self.cls(**res)



if __name__ == '__main__':
    test_json_processor()

