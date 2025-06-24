import shutil
from pathlib import Path

from ..compare import compare_files
from .utils import index_urls


def test_compare(tmp_path: Path) -> None:
    idx = index_urls(
        {
            'https://example.com': None,
            'https://en.wikipedia.org/wiki/Saturn_V': None,
            'https://plato.stanford.edu/entries/qualia': None,
        }
    )
    idx(tmp_path)
    db = tmp_path / 'promnesia.sqlite'
    old_db = tmp_path / 'promnesia-old.sqlite'
    shutil.move(str(db), str(old_db))

    idx2 = index_urls(
        {
            'https://example.com': None,
            'https://www.reddit.com/r/explainlikeimfive/comments/1ev6e0/eli5entropy': None,
            'https://en.wikipedia.org/wiki/Saturn_V': None,
            'https://plato.stanford.edu/entries/qualia': None,
        }
    )
    idx2(tmp_path)

    # should not crash, as there are more links in the new database
    assert len(list(compare_files(old_db, db))) == 0

    assert len(list(compare_files(db, old_db))) == 1
