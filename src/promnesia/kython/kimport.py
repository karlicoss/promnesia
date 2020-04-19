import importlib
import sys
from contextlib import contextmanager


@contextmanager
def extra_path(path):
    # TODO hmm, tmp_path would be a better name, but then it can be confused with FS path
    ps = str(path)
    if ps in sys.path:
        yield # no need to change anything
    else:
        sys.path.insert(0, ps)
        try:
            yield
        finally:
            sys.path.remove(ps)


# TODO and now it raises the question if it's necessary at all.. probably not so useful??
def import_from(path, name: str, package=None):
    with extra_path(path):
        return importlib.import_module(name, package=package)


def test_import_from(tmp_path):
    from pathlib import Path
    tp = Path(tmp_path)
    tm = tp / 'testmodule'
    tm.mkdir()
    tf = tm / 'testfile.py'
    tf.write_text('''
class AAA:
    passed = "PASSED"
''')
    tm = import_from(tp, 'testmodule.testfile')
    assert tm.AAA.passed == "PASSED" # type: ignore[attr-defined]
