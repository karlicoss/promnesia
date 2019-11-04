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
            'cachew', # caching with type hints
            'hug', # server

            # TODO could be optional?
            'python-magic', # for detecting mime types
            'dateparser', # TODO careful, might need python3-dev due to regex dependency?
            'logzero', # pretty colored logging
        ],
        extras_require={
            'testing': [
                 'pytest',
                 'pytest-xdist',

                 'httpie',
                 'selenium',
                 'click', # end2end test
            ],
            'linting': [
                 'pytest',
                 'pylint',
                 'mypy',
            ],
            'telegram': [
                'dataset',
            ],
            'reddit': [
                'pyjq',
            ],
        },
        package_data={name: ['py.typed']},
    )
