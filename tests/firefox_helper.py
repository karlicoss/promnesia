import os
from pathlib import Path
import re
import json
from time import sleep

# TODO share with grasp... maybe move to kython?
def open_extension_page(driver, page: str):
    ff = {
        'chrome' : get_extension_page_chrome,
        'firefox': get_extension_page_firefox,
    }[driver.name]
    extension_prefix = ff(driver=driver)
    driver.get(extension_prefix + '/' + page)


# TODO looks like it used to be posssible in webdriver api?
# at least as of 2011 https://github.com/gavinp/chromium/blob/681563ea0f892a051f4ef3d5e53438e0bb7d2261/chrome/test/webdriver/test/chromedriver.py#L35-L40
# but here https://github.com/SeleniumHQ/selenium/blob/master/cpp/webdriver-server/command_types.h there are no Extension commands
# also see driver.command_executor._commands
def get_extension_page_chrome(driver):
    chrome_profile = Path(driver.capabilities['chrome']['userDataDir'])

    # meh, don't know a better way..
    is_snap = '.org.chromium.Chromium' in str(chrome_profile)
    if is_snap:
        # under snap the path is actually inside the snap mount namespace...
        snap_tmp = Path('/tmp/snap.chromium')
        assert snap_tmp.exists(), snap_tmp
        assert os.access(snap_tmp, os.R_OK), f"You probably need to run 'chrod o+rx {snap_tmp}'"

        chrome_profile = snap_tmp / Path(*chrome_profile.parts[1:])

    prefs_file = chrome_profile / 'Default/Preferences'
    # there are some default extensions as well (e.g. cloud print)
    # also oddly enough user install extensions don't have manifest information, so we can't find it by name

    # seems to be quite a bit asynchronous (e.g. up to several seconds), so good to be defensive for a bit
    prefs = None
    addon_id = None
    for _ in range(300):
        sleep(0.05)
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
    assert prefs is not None
    return f'chrome-extension://{addon_id}'


def get_extension_page_firefox(driver):
    moz_profile = Path(driver.capabilities['moz:profile'])
    prefs_file = moz_profile / 'prefs.js'

    addon_name = 'temporary_addon'
    # TODO ok, apparently I should add it to tips on using or something..
    addon_name = 'promnesia@karlicoss.github.com'

    # doesn't appear immediately after installing somehow, so need to wait for a bit..
    addon_id = None
    for _ in range(100):
        if addon_id is not None:
            break

        sleep(0.05)
        if not prefs_file.exists():
            continue

        for line in prefs_file.read_text().splitlines():
            # temporary-addon\":\"53104c22-acd0-4d44-904c-22d11d31559a\"}")
            m = re.search(addon_name + r'.....([0-9a-z-]+)."', line)
            if m is None:
                continue
            addon_id = m.group(1)
            break
    assert addon_id is not None
    return f'moz-extension://{addon_id}'

# TODO could also check for errors
