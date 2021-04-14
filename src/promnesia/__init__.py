from pathlib import Path
from .common import PathIsh, Visit, Source, last, Loc, Results, DbVisit, Context, Res

# add deprecation warning so eventually this may converted to a namespace package?
import warnings
warnings.warn("DEPRECATED! Please import directly from 'promnesia.common', e.g. 'from promnesia.common import Visit, Source, Results'", DeprecationWarning)
