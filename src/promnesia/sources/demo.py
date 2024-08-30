'''
A dummy source, used for testing
Generates a sequence of fake evenly separated visits
'''
from __future__ import annotations

from datetime import datetime, timedelta

from promnesia.common import Results, Visit, Loc


IsoFormatDt = str
Seconds = int


# TODO allow passing isoformat string as base_dt?
# and maybe something similar as delta? start with seconds maybe
def index(
    count: int = 100,
    *,
    base_dt: datetime | IsoFormatDt = datetime.min + timedelta(days=5000),
    delta: timedelta | Seconds = timedelta(hours=1),
) -> Results:

    base_dt_ = base_dt if isinstance(base_dt, datetime) else datetime.fromisoformat(base_dt)
    delta_ = delta if isinstance(delta, timedelta) else timedelta(seconds=delta)

    # todo with some errors too?
    # todo use data generation library suggested for HPI?
    for i in range(count):
        yield Visit(
            url=f'https://demo.com/page{i}.html',
            dt=base_dt_ + delta_ * i,
            locator=Loc.make('demo'),
        )
        # todo add context?
