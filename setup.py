import sys

from pkg_resources import require, VersionConflict
from setuptools import setup

try:
    require('setuptools>=38.3')
except VersionConflict:
    print("Error: version of setuptools is too old (<38.3)!")
    sys.exit(1)


name = 'promnesia'


def building_for_pypi() -> bool:
    return sys.argv[1] == 'sdist'


if __name__ == "__main__":
    for_pypi = building_for_pypi()

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
        ],
        extras_require={
            # TODO make cachew optional?
            'optional': [
                'logzero', # pretty colored logging
            ],
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
            'org': [
                'orgparse',
            ],
            'my': [
                *([]
                  if for_pypi else # pypi doesn't like git dependencies... will think after that later
                  ['my @ git+https://github.com/karlicoss/my.git'])
            ],
        },
        package_data={name: ['py.typed']},
    )
