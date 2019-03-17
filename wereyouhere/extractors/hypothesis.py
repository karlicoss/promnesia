# extracts stuff from hypothes.is json backup
from pathlib import Path
import json
import logging
from datetime import datetime
from typing import NamedTuple, List, Optional, Union, Iterable

from wereyouhere.common import PathIsh, PreVisit, get_logger, Loc

# TODO extract to a separate hypothesis provider; reuse in my module?
def extract(json_path: PathIsh, tag='hyp') -> Iterable[PreVisit]:
    logger = get_logger()

    j = json.loads(Path(json_path).read_text())
    # TODO what I really need is my hypothesis provider... is it possible to share somehow?
    for x in j:
        [tg] = x['target'] # hopefully it's always single element
        assert tg['source'] == x['uri'] # why would they not be equal???
        url = tg['source']

        # TODO ok, it might not have selector if it's a page annotation
        sel = tg.get('selector', None)
        cparts = []
        if sel is not None:
            highlights = [s['exact'] for s in sel if 'exact' in s]
            # TODO make it a class and use self.logger?
            if len(highlights) != 1:
                logger.warning(f'{url}: weird number of highlights: {highlights}')
                # if 0, it could be an orphan. maybe safe to ignore? dunno.

            cparts.extend(highlights)

        comment = x['text'].strip()
        if comment:
            cparts.append('comment: ' + comment)

        # TODO extract tags too?
        v = PreVisit(
            url=tg['source'],
            dt=x['created'], # TODO 'updated'? # 2019-02-15T18:24:16.874113+00:00
            context='\n\n'.join(cparts),
            locator=Loc.make(json_path),
            tag=tag,
        )
        yield v
