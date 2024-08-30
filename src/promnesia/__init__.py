from .common import PathIsh, Visit, Source, last, Loc, Results, DbVisit, Context, Res  # noqa: F401

# add deprecation warning so eventually this may converted to a namespace package?
import warnings

# TODO think again about it -- what are the pros and cons?
warnings.warn("DEPRECATED! Please import directly from 'promnesia.common', e.g. 'from promnesia.common import Visit, Source, Results'", DeprecationWarning)
