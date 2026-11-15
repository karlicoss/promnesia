'''
Deprecated alias for promnesia.sources.takeout.
Uses the configured my.google.takeout.parser module.
'''

import warnings

from promnesia.common import Results


def index() -> Results:
    from .takeout import index as takeout_index

    warnings.warn(
        'promnesia.sources.takeout_legacy is deprecated; indexing with promnesia.sources.takeout instead.\n'
        'In your Promnesia config, replace promnesia.sources.takeout_legacy with promnesia.sources.takeout.\n'
        'Your existing HPI google.takeout_path setting is still used.',
        FutureWarning,
        stacklevel=2,
    )
    return takeout_index()
