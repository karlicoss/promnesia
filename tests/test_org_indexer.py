from contextlib import contextmanager
from pathlib import Path

from promnesia.indexers.org import extract_from_file

def tdata(path: str) -> Path:
    pp = Path(__file__).parent.parent / 'testdata'
    assert pp.is_dir()
    return pp.absolute() / path


def test_org_extractor():
    items = list(extract_from_file(tdata('auto/orgs/file.org')))
    assert len(items) == 2

    cpp = items[1]
    assert cpp.url == 'https://www.youtube.com/watch?v=rHIkrotSwcc'


def test_heading():
    items = list(extract_from_file(tdata('auto/orgs/file2.org')))
    assert {i.url for i in items} == {
        'https://en.wikipedia.org/wiki/Computational_topology',
        'http://graphics.stanford.edu/courses/cs468-09-fall/',
        'https://en.wikipedia.org/wiki/Triangulation_(topology)',
        'https://en.wikipedia.org/wiki/Digital_manifold',
    }
