from itertools import groupby

from promnesia.sources import auto

from common import tdata

sa2464 = 'https://www.scottaaronson.com/blog/?p=2464'

_JSON_URLS = {
    'https://johncarlosbaez.wordpress.com/2016/09/09/struggles-with-the-continuum-part-2/',
    sa2464,
}


def makemap(visits):
    key = lambda v: v.url
    def it():
        for k, g in groupby(sorted(visits, key=key), key=key):
            yield k, list(sorted(g))
    return dict(it())


def test_json():
    mm = makemap(auto.index(tdata('auto/pocket.json')))
    assert mm.keys() == _JSON_URLS

    # TODO not sure if they deserve separate visits..
    [v1, v2] = mm[sa2464]
    assert v1.context == 'list::yyy::given_url'
    assert v1.locator.href.startswith('emacs:')
    assert v1.locator.href.endswith('pocket.json')
    # TODO line number?


def test_auto():
    mm = makemap(auto.index(tdata('auto')))
    org_link = 'https://www.youtube.com/watch?v=rHIkrotSwcc'
    assert {
        *_JSON_URLS,
        org_link,
    }.issubset(mm.keys())

    [v] = mm[org_link]
    assert v.locator.href.endswith('file.org') # TODO link number or jump to heading?
    assert "xxx /r/cpp\n I've enjoyed [Chandler Carruth's" in v.context
