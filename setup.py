# see https://github.com/karlicoss/pymplate for up-to-date reference
from itertools import chain

from setuptools import setup, find_namespace_packages # type: ignore


def main() -> None:
    # works with both ordinary and namespace packages
    pkgs = find_namespace_packages('src')
    pkg = min(pkgs)
    setup(
        name=pkg,
        use_scm_version={
            'version_scheme': 'python-simplified-semver',
            'local_scheme': 'dirty-tag',
        },
        # NOTE: there is some issue on circleci windows when running pip3 install --user -e . because of setuptools_scm?
        # some CERTIFICATE_VERIFY_FAILED stuff. comment this temporary if you're debugging
        setup_requires=['setuptools_scm'],

        # otherwise mypy won't work
        # https://mypy.readthedocs.io/en/stable/installed_packages.html#making-pep-561-compatible-packages
        zip_safe=False,

        packages=pkgs, # TODO ugh. that's weird. it worked as only ['promnesia'] when installing via PIP ... but not with dev install???
        package_dir={'': 'src'},
        # necessary so that package works with mypy
        package_data={pkg: ['py.typed']},

        url='https://github.com/karlicoss/promnesia',
        author='Dmitrii Gerasimov',
        author_email='karlicoss@gmail.com',
        description='Enhancement of your browsing history',

        python_requires='>=3.7',
        install_requires=[
            'appdirs', # for portable user directories detection
            'tzlocal',
            'more_itertools',
            'pytz',
            'sqlalchemy', # DB api
            'cachew>=0.8.0', # caching with type hints

            *DEPS_INDEXER,
            *DEPS_SERVER,
        ],
        extras_require={
            'testing': [
                 'pytest',
                 'pytest-timeout',
                 'pytest-xdist', # why??

                 'psutil',

                 'httpie',   # nicer http requests (replace with curl?)
                 'selenium', # browser automations
                 'click',    # confirmations for end2end test (might remove dependency)

                 'pyautogui', # for keyboard automation during end2end tests
            ],
            'linting': [
                'pytest',

                'mypy',
                'lxml', # for coverage reports
            ],
            **{k[0]: v for k, v in DEPS_SOURCES.items()},
            'all': list(chain.from_iterable(DEPS_SOURCES.values())),
        },
        entry_points={
            'console_scripts': ['promnesia=promnesia.__main__:main'],
        }
    )

# todo might be nice to ensure they are installable in separation?
DEPS_INDEXER = [
    'urlextract',
]

DEPS_SERVER = [
    'fastapi',
    'uvicorn[standard]',
]

DEPS_SOURCES = {
    # TODO make cachew optional?
    # althrough server uses it so not sure...
    ('optional', 'dependencies that bring some bells & whistles'): [
        'logzero', # pretty colored logging
        'python-magic', # better mimetype decetion
    ],
    ('HPI'     , 'dependencies for [[https://github.com/karlicoss/HPI][HPI]]'): [
        'HPI', # pypi version
        # 'HPI @ git+https://github.com/karlicoss/hpi.git',   # uncomment to test against github version (useful for one-off CI run)
        # 'HPI @ git+file:///DUMMY/path/to/local/hpi@branch', # uncomment to test against version on the disc
        # note: sometimes you need to use file://DUMMY?? wtf?..
    ],
    ('html'    , 'dependencies for sources.html'    ): [
        'beautifulsoup4', # extracting links from the page
        'lxml'          , # bs4 backend
    ],
    ('markdown', 'dependencies for sources.markdown'): [
        'mistletoe',
    ],
    ('org'     , 'dependencies for sources.org'     ): [
        'orgparse>=0.3.0',
    ],
    ('telegram', 'dependencies for sources.telegram'): [
        'dataset',
    ],
}


if __name__ == "__main__":
    main()
