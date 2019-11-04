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
            'cachew', # caching with type hints

            # TODO could be optional?
            'logzero', # pretty colored logging

            # can remove that once get rid of kython
            'kython@git+https://github.com/karlicoss/kython.git@master',
            'typing_extensions',
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
