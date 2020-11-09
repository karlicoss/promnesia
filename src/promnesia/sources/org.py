from datetime import datetime
import re
from typing import Iterable, List, Set, Optional, Iterator, Tuple, NamedTuple, cast
from pathlib import Path


from ..common import Visit, get_logger, Results, Url, Loc, from_epoch, echain, iter_urls, PathIsh, Res, file_mtime


import orgparse
from orgparse.date import gene_timestamp_regex, OrgDate
from orgparse.node import OrgNode


CREATED_RGX = re.compile(gene_timestamp_regex(brtype='inactive'), re.VERBOSE)


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
    pp = n.properties
    createds = cast(Optional[str], pp.get('CREATED', None))
    if createds is None:
        # TODO replace with 'match', but need to strip off priority etc first?
        # see _parse_heading in orgparse
        # todo maybe use n.get_timestamps(inactive=True, point=True)? only concern is that it's searching in the body as well?
        m = CREATED_RGX.search(heading)
        if m is not None:
            createds = m.group(0) # could be None
            # todo a bit hacky..
            heading = heading.replace(createds + ' ', '')
    if createds is not None:
        [odt] = OrgDate.list_from_str(createds)
        dt = odt.start
    else:
        dt = None
    return Parsed(dt=dt, heading=heading)


def _get_heading(n: OrgNode):
    # todo not sure if it's really that useful to distinguish root and non-root...
    # maybe have a mode that returns uniform entries, and just relies on the convention
    return '' if n.is_root() else n.get_heading(format='raw')


def walk_node(*, node: OrgNode, dt: datetime) -> Iterator[Res[Tuple[Parsed, OrgNode]]]:
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


def iter_org_urls(n: OrgNode) -> Iterator[Res[Url]]:
    logger = get_logger()
    # todo not sure if it can fail? but for now, paranoid just in case
    try:
        heading = _get_heading(n)
    except Exception as e:
        logger.exception(e)
        yield e
    else:
        yield from iter_urls(heading, syntax='org')

    try:
        content = n.get_body(format='raw')
    except Exception as e:
        logger.exception(e)
        yield e
    else:
        yield from iter_urls(content, syntax='org')


def extract_from_file(fname: PathIsh) -> Results:
    """
    Note that org-mode doesn't keep timezone, so we don't really have choice but make it tz-agnostic
    """
    path = Path(fname)
    o = orgparse.load(path)
    root = o.root

    fallback_dt = file_mtime(path)

    ex = RuntimeError(f'while extracting from {fname}')

    for wr in walk_node(node=root, dt=fallback_dt):
        if isinstance(wr, Exception):
            yield echain(ex, wr)
            continue

        (parsed, node) = wr
        dt = parsed.dt
        assert dt is not None # shouldn't be because of fallback
        for r in iter_org_urls(node):
            # TODO get body recursively? not sure
            try:
                # maybe use a similar technique as in exercise parser? e.g. descent until we mee a candidate that worth a separate context?
                tagss = '' if len(node.tags) == 0 else f'   :{":".join(sorted(node.tags))}:'
                # TODO not sure... perhaps keep the whole heading intact? unclear how to handle file tags though
                ctx = parsed.heading + tagss + '\n' + node.get_body(format='raw')
            except Exception as e:
                yield echain(ex, e)
                ctx = 'ERROR' # TODO more context?

            if isinstance(r, Url):
                yield Visit(
                    url=r,
                    dt=dt,
                    locator=Loc.file(fname, line=node.linenumber),
                    context=ctx,
                )
            else: # error
                yield echain(ex, r)
