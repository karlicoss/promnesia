from typing import Optional

from promnesia.common import Visit
from promnesia.sources.org import extract_from_file

from common import tdata, throw

def declrf(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    # meh.. not sure how ot handle this properly, ideally should be via pytest?
    # not sure if should just do it in the indexer? e.g. extension might not like it
    return s.replace('\r', '')


def test_org_indexer() -> None:
    [_, cpp, cozy] = [v if isinstance(v, Visit) else throw(v) for v in extract_from_file(tdata('auto/orgs/file.org'))]

    assert cpp.url == 'https://www.youtube.com/watch?v=rHIkrotSwcc'
    # TODO not sure about filetags?
    exp = '''
xxx /r/cpp   :cpp:programming:
 I've enjoyed [Chandler Carruth's _There Are No Zero-cost Abstractions_](
 https://www.youtube.com/watch?v=rHIkrotSwcc) very much.

'''.lstrip()
    assert declrf(cpp.context) == exp

    assert cozy.url == 'https://twitter.com/Mappletons/status/1255221220263563269'


def test_org_indexer_2() -> None:
    items = [v if isinstance(v, Visit) else throw(v) for v in extract_from_file(tdata('auto/orgs/file3.org'))]

    assert len(items) == 6
    assert items[0].url == 'https://www.reddit.com/r/androidapps/comments/4i36z9/how_you_use_your_android_to_the_maximum/d2uq24i'
    assert items[1].url == 'https://link.com'
    assert items[-2].url == 'https://en.wikipedia.org/wiki/Resilio_Sync'
    # TODO shit def need org specific url extractor (and then extract from everything remaining)
    # assert results[-1].url == 'https://en.wikipedia.org/wiki/InterPlanetary_File_System'


def test_heading() -> None:
    items = [v if isinstance(v, Visit) else throw(v) for v in extract_from_file(tdata('auto/orgs/file2.org'))]
    assert {i.url for i in items} == {
        'https://en.wikipedia.org/wiki/Computational_topology',
        'http://graphics.stanford.edu/courses/cs468-09-fall/',
        'https://en.wikipedia.org/wiki/Triangulation_(topology)',
        'https://en.wikipedia.org/wiki/Digital_manifold',
    }


def test_url_in_properties() -> None:
    items = [v if isinstance(v, Visit) else throw(v) for v in extract_from_file(tdata('auto/orgs/file4.org'))]

    assert len(items) == 2, items
    assert items[0].url == 'https://example.org/ref_example'
    assert items[1].url == 'http://example.org/a_test'
