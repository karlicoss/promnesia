'''
A dummy source, used for testing
Generates a sequence of fake evenly separated visits
'''

from datetime import datetime, timedelta

from ..common import Results, Visit, Loc


def index(count: int=100, *, base_dt: datetime=datetime.min + timedelta(days=5000), delta: timedelta=timedelta(hours=1)) -> Results:
    # todo with some errors too?
    # todo use data generation library suggested for HPI?
    for i in range(count):
        yield Visit(
            url=f'https://demo.com/page{i}.html',
            dt=base_dt + delta * i,
            locator=Loc.make('demo'),
        )
        # todo add context?
