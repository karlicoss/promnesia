from promnesia.indexers import auto

from common import tdata

_JSON_URLS = {
    # TODO FIXME only extract one of them?
    'https://johncarlosbaez.wordpress.com/2016/09/09/struggles-with-the-continuum-part-2/',
    'https://www.scottaaronson.com/blog/?p=2464',
}

def test_json():
    assert set(x.url for x in auto.index(tdata('auto/pocket.json'))) == _JSON_URLS
