from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path

from ..common import Loc, Source, Visit
from ..database.dump import visits_to_sqlite
from ..extract import extract_visits

# TODO a bit shit... why did I make it dict at first??
Urls = Mapping[str, str | None] | Sequence[tuple[str, str | None]]


def index_urls(urls: Urls, *, source_name: str = 'test'):
    uuu = list(urls.items()) if isinstance(urls, dict) else urls

    def idx(tmp_path: Path) -> None:
        def indexer():
            # pick somewhat reasonable datetime here; otherwise javascript may not parse it properly
            start_dt = datetime(1980, 1, 1)
            for i, (url, ctx) in enumerate(uuu):
                yield Visit(
                    url=url,
                    dt=start_dt + timedelta(hours=i),
                    locator=Loc.make('test'),
                    context=ctx,
                )

        db_visits = extract_visits(source=Source(indexer), src=source_name)
        errors = visits_to_sqlite(vit=db_visits, overwrite_db=True, _db_path=tmp_path / 'promnesia.sqlite')

        assert len(errors) == 0, errors

    return idx
