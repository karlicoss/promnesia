import pkgutil
import promnesia.sources as pkg


def test_imports():
    '''
    Check that we at least have all necessary dependencies. Although it doesn't "really" guarantee anything?
    '''
    for importer, name, ispkg in pkgutil.walk_packages(
            path=pkg.__path__,
            prefix=pkg.__name__+'.'
    ):
        print(name)
