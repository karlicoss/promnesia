'''
A dummy source, used for testing
Generates a sequence of fake evenly separated visits
'''

from ..common import Results, Visit, Loc
from datetime import datetime, timedelta


def index(count=100, *, base_dt: datetime=datetime.min + timedelta(days=5000), delta=timedelta(hours=1)) -> Results:
    # todo with some errors too?
    # todo use data generation library suggested for HPI?
    for i in range(count):
        yield Visit(
            url=f'https://demo.com/page{i}.html',
            dt=base_dt + delta * i,
            locator=Loc.make('demo'),
        )
        # todo add context?
