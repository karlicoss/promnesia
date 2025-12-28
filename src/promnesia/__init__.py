def __getattr__(name: str):
    # for backward compatibility
    deprecated_imports = [
        'Context',
        'DbVisit',
        'Loc',
        'PathIsh',
        'Res',
        'Results',
        'Source',
        'Visit',
        'last',
    ]
    if name in deprecated_imports:
        import warnings

        warnings.warn(
            "DEPRECATED! Import directly from 'promnesia.common', e.g. 'from promnesia.common import Visit, Source, Results'",
            DeprecationWarning,
        )

        from . import common

        return getattr(common, name)

    # need to raise so other imports can proceed as usual
    raise AttributeError
