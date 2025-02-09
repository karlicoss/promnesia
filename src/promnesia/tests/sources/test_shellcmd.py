import pytest

from ...common import Source, _is_windows
from ...extract import extract_visits
from ...sources import shellcmd
from ..common import get_testdata


@pytest.mark.skipif(_is_windows, reason="no grep on windows")
def test_via_grep() -> None:

    visits = list(
        extract_visits(
            Source(
                shellcmd.index,
                # meh. maybe should deprecate plain string here...
                r"""grep -Eo -r --no-filename (http|https)://\S+ """ + str(get_testdata('custom')),
            ),
            src='whatever',
        )
    )
    # TODO I guess filtering of equivalent urls should rather be tested on something having context (e.g. org mode)
    assert len(visits) == 5
