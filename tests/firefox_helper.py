from pathlib import Path
import re
from time import sleep


# copy pasted from grasp

def open_extension_page(driver, page: str):
    moz_profile = Path(driver.capabilities['moz:profile'])
    prefs_file = moz_profile / 'prefs.js'

    # doesn't appear immediately after installing somehow, so need to wait for a bit..
    for _ in range(10):
        sleep(0.5)
        if prefs_file.exists():
            break

    addon_id = None
    for line in prefs_file.read_text().splitlines():
        # temporary-addon\":\"53104c22-acd0-4d44-904c-22d11d31559a\"}")
        m = re.search(r'temporary-addon.....([0-9a-z-]+)."', line)
        if m is None:
            continue
        addon_id = m.group(1)
    assert addon_id is not None

    page = f'moz-extension://{addon_id}/{page}'
    driver.get(page)

# TODO could also check for errors
