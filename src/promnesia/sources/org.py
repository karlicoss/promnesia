from datetime import datetime
import re
from typing import Iterable, List, Set, Optional, Iterator, Union, Tuple, NamedTuple
from pathlib import Path


from ..common import Visit, get_logger, Results, Url, Loc, from_epoch, echain, extract_urls, PathIsh


import orgparse # type: ignore
from orgparse.date import gene_timestamp_regex, OrgDate # type: ignore
from orgparse.node import OrgNode # type: ignore


rgx = re.compile(gene_timestamp_regex(brtype='inactive'), re.VERBOSE)


# TODO should be include child note contents??
# e.g. what to do with
"""
* something .... http://reddit.org
** subnote
** subnote
"""

class Parsed(NamedTuple):
    dt: Optional[datetime]
    heading: str

def _parse_node(n: OrgNode) -> Parsed:
    if n.is_root():
        return Parsed(dt=None, heading='')

    heading = n.get_heading('raw')
    pp = n.properties or {}
    createds = pp.get('CREATED', None)
    if createds is None:
        # TODO replace with 'match', but need to strip off priority etc first?
        # see _parse_heading in orgparse
        m = rgx.search(heading)
        if m is not None:
            createds = m.group(0) # could be None
            # TODO a bit hacky..
            heading = heading.replace(createds + ' ', '')
    if createds is not None:
        [odt] = OrgDate.list_from_str(createds)
        dt = odt.start
    else:
        dt = None
    return Parsed(dt=dt, heading=heading)


def _get_heading(n: OrgNode):
    return '' if n.is_root() else n.get_heading(format='raw') # TODO convert links to html?


# TODO maybe line by line? or restrict length? not sure..
def _get_body(n: OrgNode):
    if n.is_root():
        return '\n'.join(n._lines)
    else:
        return n.get_body(format='raw')


def walk_node(*, node: OrgNode, dt: datetime) -> Iterator[Union[Tuple[Parsed, OrgNode], Exception]]:
    try:
        parsed = _parse_node(node)
    except Exception as e:
        yield e
    else:
        if parsed.dt is None:
            parsed = parsed._replace(dt=dt)
        else:
            dt = parsed.dt
    yield parsed, node

    for c in node.children:
        yield from walk_node(node=c, dt=dt)


def iter_urls(n: OrgNode) -> Iterator[Union[Url, Exception]]:
    logger = get_logger()
    try:
        heading = _get_heading(n)
    except Exception as e:
        logger.exception(e)
        yield e
    else:
        yield from extract_urls(heading, syntax='org')

    try:
        content = _get_body(n)
    except Exception as e:
        logger.exception(e)
        yield e
    else:
        yield from extract_urls(content, syntax='org')


def extract_from_file(fname: PathIsh) -> Results:
    """
    Note that org-mode doesn't keep timezone, so we don't really have choice but make it tz-agnostic
    """
    path = Path(fname)
    o = orgparse.loads(path.read_text())
    # meh. but maybe ok to start with?
    root = o.root

    fallback_dt = datetime.fromtimestamp(path.stat().st_mtime)

    ex = RuntimeError(f'while extracting from {fname}')

    for wr in walk_node(node=root, dt=fallback_dt):
        if isinstance(wr, Exception):
            yield echain(ex, wr)
            continue

        (pn, n) = wr
        dt = pn.dt
        assert dt is not None # shouldn't be because of fallback
        for r in iter_urls(n):
            try:
                # TODO get body recursively? not sure
                ctx = pn.heading + '\n' + _get_body(n)
            except Exception as e:
                yield echain(ex, e)
                ctx = 'ERROR' # TODO more context?

            if isinstance(r, Url):
                yield Visit(
                    url=r,
                    dt=dt,
                    locator=Loc.file(fname), # TODO line number
                    context=ctx,
                )
            else: # error
                yield echain(ex, r)
