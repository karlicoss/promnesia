import pkgutil
import promnesia.sources as pkg

import importlib


def test_imports():
    '''
    Check that we at least have all necessary dependencies. Although it doesn't "really" guarantee anything?
    '''
    for importer, name, ispkg in pkgutil.walk_packages(
            path=pkg.__path__,
            prefix=pkg.__name__+'.'
    ):
        importlib.import_module(name)


def test_imports_lazy():
    for importer, name, ispkg in pkgutil.walk_packages(
            path=pkg.__path__,
            prefix=pkg.__name__+'.'
    ):
        last = name.split('.')[-1]
        # hopefully for these VVV you know what are you doing and specify the deps
        # TODO maybe add check_dependencies thing?
        if last in {
                'html',
                'markdown',
                'org',
        }:
            continue
        importlib.import_module(name)
