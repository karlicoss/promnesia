from ...common import Source
from ...extract import extract_visits
from ...sources import plaintext, shellcmd
from ..common import get_testdata, unwrap


def test_plaintext_path_extractor() -> None:
    visits = list(extract_visits(
        Source(
            shellcmd.index,
            plaintext.extract_from_path(get_testdata('custom')),
        ),
        src='whatever',
    ))
    assert {unwrap(v).orig_url for v in visits} == {
        'http://google.com',
        'http://google.com/',
        'http://some-weird-domain.xyz/whatever',
        'https://google.com',
        'http://what.about.this.link',
    }

    [wa] = [v for v in visits if unwrap(v).orig_url == 'http://what.about.this.link']
    f2 = get_testdata('custom') / 'file2.txt'
    assert unwrap(wa).locator.href == f'editor://{f2}:3'  # occurs line 3
