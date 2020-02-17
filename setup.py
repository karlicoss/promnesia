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
            # althrough server uses it so not sure...
            'optional': [
                'logzero', # pretty colored logging
            ],
            'testing': [
                 'pytest',
                 'pytest-xdist', # why??

                 'httpie',   # nicer http requests (replace with curl?)
                 'selenium', # browser automations
                 'click',    # confirmations for end2end test (might remove dependency)
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
            'html': [
                'beautifulsoup4', # extracting links from the page
            ],
            'my': [
                *([]
                  if for_pypi else # pypi doesn't like git dependencies... will think after that later
                  ['my @ git+https://github.com/karlicoss/my.git'])
            ],
        },
        package_data={name: ['py.typed']},
        entry_points={
            'console_scripts': ['promnesia=promnesia.__main__:main'],
        }
    )
