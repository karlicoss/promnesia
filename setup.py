# see https://github.com/karlicoss/pymplate for up-to-date reference


from setuptools import setup, find_packages # type: ignore

DEPS_INDEXER = [
    'urlextract',
    # TODO could be optional?
    'python-magic', # for detecting mime types
]

DEPS_SERVER = [
    'tzlocal',
    'hug',
]

def main():
    pkgs = find_packages('src')
    # [pkg] = pkgs
    pkg = 'promnesia' # eh, find some subpackages too?
    setup(
        name=pkg,
        use_scm_version={
            'version_scheme': 'python-simplified-semver',
            'local_scheme': 'dirty-tag',
        },
        setup_requires=['setuptools_scm'],

        zip_safe=False,

        packages=pkgs, # TODO ugh. that's weird. it worked as only ['promnesia'] when installing via PIP ... but not with dev install???
        package_dir={'': 'src'},
        package_data={pkg: ['py.typed']},

        url='https://github.com/karlicoss/promnesia',
        author='Dmitrii Gerasimov',
        author_email='karlicoss@gmail.com',
        description='Enhancement of your browsing history',

        install_requires=[
            *DEPS_INDEXER,
            *DEPS_SERVER,
            'more_itertools',
            'pytz',
            'sqlalchemy', # DB api
            'cachew', # caching with type hints
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
            'markdown': [
                'mistletoe',
            ],
            'org': [
                'orgparse',
            ],
            'html': [
                'beautifulsoup4', # extracting links from the page
                'lxml', # bs4 backend
            ],
            'HPI': [
                'HPI', # pypi version
                # 'HPI @ git+https://github.com/karlicoss/hpi.git', # uncomment to test against github version (useful for one-off CI run)
                # 'HPI @ git+file://DUMMY/path/to/local/hpi'    , # uncomment to test against version on the disc
            ],
            # TODO make 'all' group?
        },
        entry_points={
            'console_scripts': ['promnesia=promnesia.__main__:main'],
        }
    )


if __name__ == "__main__":
    main()
