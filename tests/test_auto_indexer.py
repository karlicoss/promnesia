from itertools import groupby
import os

from promnesia.sources import auto

from common import tdata, throw

sa2464 = 'https://www.scottaaronson.com/blog/?p=2464'

_JSON_URLS = {
    'https://johncarlosbaez.wordpress.com/2016/09/09/struggles-with-the-continuum-part-2/',
    sa2464,
}


def makemap(visits):
    key = lambda v: v.url
    def it():
        vit = (throw(v) if isinstance(v, Exception) else v for v in visits)
        for k, g in groupby(sorted(vit, key=key), key=key):
            yield k, list(sorted(g))
    return dict(it())


def test_json() -> None:
    mm = makemap(auto.index(
        tdata('auto'),
        ignored='*/orgs/*',
    ))
    assert mm.keys() == _JSON_URLS

    # TODO not sure if they deserve separate visits..
    [v1, v2] = mm[sa2464]
    assert v1.context == 'list::yyy::given_url'
    # todo not sure if editor:// work on Windows
    assert v1.locator.href.startswith('editor://')
    assert v1.locator.href.endswith('pocket.json')
    # TODO line number?


def test_auto() -> None:
    mm = makemap(auto.index(tdata('auto')))
    org_link = 'https://www.youtube.com/watch?v=rHIkrotSwcc'
    assert {
        *_JSON_URLS,
        org_link,
    }.issubset(mm.keys())

    [v] = mm[org_link]
    assert v.locator.title == 'orgs' + os.sep + 'file.org:14' # meh
    assert v.locator.href.endswith('file.org:14')
    assert "xxx /r/cpp" in v.context
    assert "I've enjoyed [Chandler Carruth's" in v.context


def test_obsidian() -> None:
    mm = makemap(auto.index(tdata('obsidian-vault')))
    example_url = 'https://example.com'
    [v] = mm[example_url]
    assert v.locator.href.startswith('obsidian://')


def test_logseq() -> None:
    mm = makemap(auto.index(tdata('logseq-graph')))
    example_url = 'https://example.com'
    [v] = mm[example_url]
    assert v.locator.href.startswith('logseq://')
