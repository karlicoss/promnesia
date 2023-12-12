from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple, Union

from ..common import Source, Loc, Visit
from ..database.dump import visits_to_sqlite
from ..extract import extract_visits


# TODO a bit shit... why did I make it dict at first??
Urls = Union[
           Mapping[str, Optional[str]],
    Sequence[Tuple[str, Optional[str]]],
]


def index_urls(urls: Urls, *, source_name: str = 'test'):
    uuu = list(urls.items()) if isinstance(urls, dict) else urls

    def idx(tmp_path: Path) -> None:
        def indexer():
            for i, (url, ctx) in enumerate(uuu):
                yield Visit(
                    url=url,
                    dt=datetime.min + timedelta(days=5000) + timedelta(hours=i),
                    locator=Loc.make('test'),
                    context=ctx,
                )

        db_visits = extract_visits(source=Source(indexer), src=source_name)
        errors = visits_to_sqlite(vit=db_visits, overwrite_db=True, _db_path=tmp_path / 'promnesia.sqlite')

        assert len(errors) == 0, errors

    return idx
