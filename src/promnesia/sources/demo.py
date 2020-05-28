'''
A dummy source, used for testing
'''

from .. import Results, Visit, Loc
from datetime import datetime, timedelta


def index(count=100) -> Results:
    # todo with some errors too?
    # todo use data generation library suggested for HPI?
    for i in range(count):
        yield Visit(
            url=f'https://demo.com/page{i}.html',
            dt=datetime.min + timedelta(days=5000) + timedelta(hours=i),
            locator=Loc.make('demo'),
        )
        # todo add context?
