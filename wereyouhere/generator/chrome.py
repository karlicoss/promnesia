import csv
from datetime import datetime
from subprocess import check_output
from typing import List, Dict, Set, NamedTuple, Iterator
from urllib.parse import unquote

import pytz

from wereyouhere.common import Entry, History, Visit

# def iter_chrome_histories(chrome_db: str, tag: str):
#     import magic # type: ignore
#     mime = magic.Magic(mime=True)
#     m = mime.from_file(chrome_db)
#     assert m == 'application/x-sqlite3'
#     yield read_chrome_history(chrome_db, tag)
