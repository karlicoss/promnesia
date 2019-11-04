import sys

from pkg_resources import require, VersionConflict
from setuptools import setup

try:
    require('setuptools>=38.3')
except VersionConflict:
    print("Error: version of setuptools is too old (<38.3)!")
    sys.exit(1)


name = 'promnesia'

if __name__ == "__main__":
    setup(
        use_pyscaffold=True,
        install_requires=[
            'pytz',
            'urlextract',
            'sqlalchemy', # DB api
            'hug', # server
            'python-magic', # for detecting mime types
            'dateparser',

            # TODO could be optional?
            'logzero', # pretty colored logging

            # TODO make these optional:
            'dataset', # used by some indexers
            'pyjq', # json extraction
            'cachew', # caching

            # TODO get rid of logzero?
            'logzero',

            # TODO vendorize
            'kython@git+https://github.com/karlicoss/kython.git@master',
            # can remove that once get rid of kython
            'typing_extensions',
        ],
        extras_require={
            'testing': [
                 'pytest',
                 'pytest-xdist',

                 'httpie',
                 'selenium',
                 'click', # end2end test
                 'getch', # for end2end test
            ],
            'linting': [
                 'pytest',
                 'pylint',
                 'mypy',
            ],
        },
        package_data={name: ['py.typed']},
    )
