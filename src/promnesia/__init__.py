# add deprecation warning so eventually this may converted to a namespace package?
import warnings

from .common import (  # noqa: F401
    Context,
    DbVisit,
    Loc,
    PathIsh,
    Res,
    Results,
    Source,
    Visit,
    last,
)

# TODO think again about it -- what are the pros and cons?
warnings.warn("DEPRECATED! Please import directly from 'promnesia.common', e.g. 'from promnesia.common import Visit, Source, Results'", DeprecationWarning)
