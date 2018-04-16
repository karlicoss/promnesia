from datetime import datetime, timedelta
import json
import os.path
from typing import List

from .common import History, Entry, Visit

def render(all_histories: List[History], where: str) -> None:
    from wereyouhere.common import merge_histories
    res = merge_histories(all_histories)

    # sort visits by datetime, sort all items by URL
    entries = [
        entry._replace(visits=sorted(entry.visits)) for _, entry in sorted(res.items())
    ]
    # # TODO filter somehow; sort and remove google queries, etc
    # # TODO filter by length?? or by query length (after ?)

    def format_entry(e: Entry) -> List[str]:
        visits = e.visits

        delta = timedelta(minutes=20)
        groups: List[List[Visit]] = []
        group: List[Visit] = []
        def dump_group():
            nonlocal group
            if len(group) > 0:
                groups.append(group)
                group = []
        for v in visits:
            last = v if len(group) == 0 else group[-1]
            if v.dt - last.dt <= delta:
                group.append(v)
            else:
                dump_group()
        dump_group()

        FORMAT = "%d %b %Y %H:%M"
        res = []
        for group in groups:
            tags = {e.tag for e in group}
            stags = ':'.join(tags)

            if len(group) == 1:
                res.append("{} ({})".format(group[0].dt.strftime(FORMAT), stags))
            else:
                # TODO maybe, show minutes?..
                res.append("{}--{} ({})".format(group[0].dt.strftime(FORMAT), group[-1].dt.strftime("%H:%M"), stags))
        # we presumably want descending date!
        return list(reversed(res))


    json_dict = {
        e.url: format_entry(e)
        for e in entries
    }
    with open(where, 'w') as fo:
        json.dump(json_dict, fo, indent=1)
    pass
