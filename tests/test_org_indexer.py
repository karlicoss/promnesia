from promnesia.sources.org import extract_from_file

from common import tdata

def test_org_indexer():
    items = list(extract_from_file(tdata('auto/orgs/file.org')))
    assert len(items) == 3

    cpp = items[1]
    assert cpp.url == 'https://www.youtube.com/watch?v=rHIkrotSwcc'

    cozy = items[2]
    assert cozy.url == 'https://twitter.com/Mappletons/status/1255221220263563269'


def test_org_indexer_2():
    items = list(extract_from_file(tdata('auto/orgs/file3.org')))

    assert len(items) == 6
    for i in items:
        assert i.dt.tzinfo is None, i
    assert items[0].url == 'https://www.reddit.com/r/androidapps/comments/4i36z9/how_you_use_your_android_to_the_maximum/d2uq24i'
    assert items[1].url == 'https://link.com'
    assert items[-2].url == 'https://en.wikipedia.org/wiki/Resilio_Sync'
    # TODO shit def need org specific url extractor (and then extract from everything remaining)
    # assert results[-1].url == 'https://en.wikipedia.org/wiki/InterPlanetary_File_System'


def test_heading():
    items = list(extract_from_file(tdata('auto/orgs/file2.org')))
    assert {i.url for i in items} == {
        'https://en.wikipedia.org/wiki/Computational_topology',
        'http://graphics.stanford.edu/courses/cs468-09-fall/',
        'https://en.wikipedia.org/wiki/Triangulation_(topology)',
        'https://en.wikipedia.org/wiki/Digital_manifold',
    }


