from datetime import datetime
import re
from typing import Iterable, List, Set, Optional, Iterator, Tuple, NamedTuple, cast
from pathlib import Path


from ..common import Visit, get_logger, Results, Url, Loc, from_epoch, iter_urls, PathIsh, Res, file_mtime


import orgparse
from orgparse.date import gene_timestamp_regex, OrgDate
from orgparse.node import OrgNode


UPDATE_ORGPARSE_WARNING = 'WARNING: please update orgparse version to a more recent (pip3 install -U orgparse)'

_warned = False
def warn_old_orgparse_once() -> Iterable[Exception]:
    global _warned
    if _warned:
        return []
    _warned = True
    # NOTE: can't use pkg_resources because the module might be available even without being properly installed..
    return [RuntimeError(UPDATE_ORGPARSE_WARNING)]


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


def get_body_compat(node: OrgNode) -> str:
    try:
        return node.get_body(format='raw')
    except Exception as e:
        if node.is_root():
            # get_body was only added to root in 0.2.0
            for x in warn_old_orgparse_once():
                # ugh. really crap, but it will at least only warn once... (becaue it caches)
                raise x
            return UPDATE_ORGPARSE_WARNING
        else:
            raise e


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
        values = n.properties.values()
    except Exception as e:
        logger.exception(e)
        yield e
    else:
        for v in values:
            yield from iter_urls(str(v), syntax='org')

    try:
        content = get_body_compat(n)
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
    o = orgparse.load(str(path))
    root = o.root

    fallback_dt = file_mtime(path)

    for wr in walk_node(node=root, dt=fallback_dt):
        if isinstance(wr, Exception):
            yield wr
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
                ctx = parsed.heading + tagss + '\n' + get_body_compat(node)
            except Exception as e:
                yield e
                ctx = 'ERROR' # TODO more context?

            if isinstance(r, Url):
                yield Visit(
                    url=r,
                    dt=dt,
                    locator=Loc.file(
                        fname,
                        line=getattr(node, 'linenumber', None), # make it defensive so it works against older orgparse (pre 0.2)
                    ),
                    context=ctx,
                )
            else: # error
                yield r
