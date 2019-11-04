from pathlib import Path
from typing import Union

PathIsh = Union[Path, str]

def open(path: PathIsh, *args, **kwargs): # TODO is it bytes stream??
    pp = Path(path)
    suf = pp.suffix
    if suf in ('.xz',):
        import lzma
        return lzma.open(pp, *args, **kwargs)
    elif suf in ('.zip',):
        from zipfile import ZipFile
        return ZipFile(pp).open(*args, **kwargs)
    elif suf in ('.lz4',):
        # pylint: disable=import-error
        import lz4.frame # type: ignore
        return lz4.frame.open(str(pp))
    else:
        return pp.open(*args, **kwargs)

