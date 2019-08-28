from pathlib import Path
import re
import json
from time import sleep


# TODO can extract hotkeys from Preferences file too ['extensions'] / commands / 
# "path": "/tmp/.org.chromium.Chromium.TKhNoq/extension_ceedkmkoeooncekjljapnkkjhldddcid",
#     "commands": {
#            "linux:Ctrl+Shift+V": {
#                "command_name": "show_dots",
#                "extension": "ceedkmkoeooncekjljapnkkjhldddcid",
#                "global": false
#            }
#        },


# copy pasted from grasp


def open_extension_page(driver, page: str):
    ff = {
        'chrome' : get_extension_page_chrome,
        'firefox': get_extension_page_firefox,
    }[driver.name]
    extension_prefix = ff(driver=driver)
    driver.get(extension_prefix + '/' + page)


def get_extension_page_chrome(driver):
    chrome_profile = Path(driver.capabilities['chrome']['userDataDir'])
    prefs_file = chrome_profile / 'Default/Preferences'
    # there are some default extensions as well (e.g. cloud print)
    # also oddly enough user install extensions don't have manifest information, so we can't find it by name

    # seems to be quite a bit asynchronous (e.g. up to several seconds), so good to be defensive for a bit
    addon_id = None
    for _ in range(30):
        sleep(0.5)
        if not prefs_file.exists():
            continue

        prefs = json.loads(prefs_file.read_text())
        settings = prefs.get('extensions', {}).get('settings', None)
        if settings is None:
            continue

        addon_ids = [k for k, v in settings.items() if Path(v['path']).name == f'extension_{k}']
        if len(addon_ids) == 0:
            print('addon_ids is none')
            continue
        [addon_id] = addon_ids
    assert addon_id is not None
    return f'chrome-extension://{addon_id}'


def get_extension_page_firefox(driver):
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
    return f'moz-extension://{addon_id}'

# TODO could also check for errors
