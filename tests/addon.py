"""
Promnesia-specific addon wrappers
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import sleep

import pytest
from addon_helper import AddonHelper
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Remote as Driver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait as Wait
from webdriver_utils import frame_context, is_visible, wait_for_alert

from promnesia.logging import LazyLogger

logger = LazyLogger('promnesia-tests', level='debug')


from promnesia.common import measure as measure_orig


@contextmanager
def measure(*args, **kwargs):
    kwargs['logger'] = logger
    with measure_orig(*args, **kwargs) as m:
        yield m


def get_addon_source(kind: str) -> Path:
    # TODO compile first?
    addon_path = (Path(__file__).parent.parent / 'extension' / 'dist' / kind).absolute()
    assert addon_path.exists()
    assert (addon_path / 'manifest.json').exists()
    return addon_path


LOCALHOST = 'http://localhost'


class Command:
    # TODO assert these against manifest?
    ACTIVATE = '_execute_browser_action'
    ACTIVATE_V3 = '_execute_action'
    MARK_VISITED = 'mark_visited'
    SEARCH = 'search'


PROMNESIA_SIDEBAR_ID = 'promnesia-sidebar'


@dataclass
class Sidebar:
    addon: Addon

    @property
    def driver(self) -> Driver:
        return self.addon.helper.driver

    @contextmanager
    def ctx(self) -> Iterator[WebElement]:
        selector = (By.XPATH, '//iframe[contains(@id, "promnesia-frame")]')
        wait = 5  # if you want to decrease this, make sure test_sidebar_navigation isn't failing
        frame_element = Wait(self.driver, timeout=wait).until(
            EC.presence_of_element_located(selector),
        )

        # frames = self.driver.find_elements(*selector)
        # TODO uncomment it later when sidebar is injected gracefully...
        # assert len(frames) == 1, frames  # just in case

        frame_id = frame_element.get_attribute('id')
        with frame_context(self.driver, frame_id) as frame:
            assert frame is not None
            yield frame

    @property
    def available(self) -> bool:
        try:
            with self.ctx():
                return True
        except TimeoutException:
            return False

    @property
    def visible(self) -> bool:
        loc = (By.ID, PROMNESIA_SIDEBAR_ID)
        with self.ctx():
            Wait(self.driver, timeout=5).until(EC.presence_of_element_located(loc))
            # NOTE: document in JS here is in the context of iframe
            return is_visible(self.driver, self.driver.find_element(*loc))

    def open(self) -> None:
        assert not self.visible
        self.addon.activate()

        with measure('Sidebar.open') as m:
            while not self.visible:
                assert m() <= 10, 'timeout'
                sleep(0.001)

    def close(self) -> None:
        assert self.visible
        self.addon.activate()
        with measure('Sidebar.close') as m:
            while self.visible:
                assert m() <= 10, 'timeout'
                sleep(0.001)

    @property
    def filters(self) -> list[WebElement]:
        # TODO hmm this only works within sidebar frame context
        # but if we add with self.ctx() here, it seems unhappy with enterinng the context twice
        # do something about it later..
        outer = self.driver.find_element(By.ID, 'promnesia-sidebar-filters')
        return outer.find_elements(By.CLASS_NAME, 'src')

    @property
    def visits(self) -> list[WebElement]:
        return self.driver.find_elements(By.XPATH, '//*[@id="visits"]/li')

    def trigger_search(self) -> None:
        # this should be the window with extension
        cur_window_handles = self.driver.window_handles
        with self.ctx():
            self.driver.find_element(By.ID, 'button-search').click()
            self.addon.wait_for_search_tab(cur_window_handles)

    def trigger_mark_visited(self) -> None:
        with self.ctx():
            self.driver.find_element(By.ID, 'button-mark').click()

    def trigger_close(self) -> None:
        with self.ctx():
            self.driver.find_element(By.ID, 'button-close').click()


@dataclass
class OptionsPage:
    helper: AddonHelper

    def open(self) -> None:
        self.helper.open_page(self.helper.options_page_name)

        # make sure settings are loaded first -- otherwise we might get race conditions when we try to set them in tests
        Wait(self.helper.driver, timeout=5).until(EC.presence_of_element_located((By.ID, 'promnesia-settings-loaded')))

    def configure_extension(
        self,
        *,
        host: str | None = None,
        port: str | None = None,
        show_dots: bool = True,
        highlights: bool | None = None,
        blacklist: Sequence[str] | None = None,
        excludelists: Sequence[str] | None = None,
        notify_contexts: bool | None = None,
        position: str | None = None,
        verbose_errors: bool = True,
    ) -> None:
        driver = self.helper.driver

        def set_checkbox(cid: str, value: bool) -> None:  # noqa: FBT001
            cb = driver.find_element(By.ID, cid)
            selected = cb.is_selected()
            if selected != value:
                cb.click()

        # TODO log properly
        print(f"Setting: port {port}, show_dots {show_dots}")

        self.open()

        if host is not None or port is not None:
            self._set_endpoint(host=host, port=port)

        if show_dots is not None:
            set_checkbox('mark_visited_always_id', show_dots)

        # TODO not sure, should be False for demos?
        set_checkbox('verbose_errors_id', verbose_errors)

        if highlights is not None:
            set_checkbox('highlight_id', highlights)

        if notify_contexts is not None:
            set_checkbox('contexts_popup_id', notify_contexts)

        if position is not None:
            self._set_position(position)

        if blacklist is not None:
            bl = driver.find_element(By.ID, 'global_excludelist_id')  # .find_element_by_tag_name('textarea')
            bl.click()
            # ugh, that's hacky. presumably due to using Codemirror?
            bla = driver.switch_to.active_element
            # ugh. doesn't work, .text always returns 0...
            # if len(bla.text) > 0:
            # for some reason bla.clear() isn't working...
            # results in ElementNotInteractableException: Element <textarea> could not be scrolled into view
            bla.send_keys(Keys.CONTROL + 'a')
            bla.send_keys(Keys.BACKSPACE)
            bla.send_keys('\n'.join(blacklist))

        if excludelists is not None:
            excludelists_json = json.dumps(excludelists)

            bl = driver.find_element(By.ID, 'global_excludelists_ext_id')  # .find_element_by_tag_name('textarea')
            bl.click()
            # ugh, that's hacky. presumably due to using Codemirror?
            bla = driver.switch_to.active_element
            # ugh. doesn't work, .text always returns 0...
            # if len(bla.text) > 0:
            # for some reason bla.clear() isn't working...
            # results in ElementNotInteractableException: Element <textarea> could not be scrolled into view
            bla.send_keys(Keys.CONTROL + 'a')
            bla.send_keys(Keys.BACKSPACE)
            bla.send_keys(excludelists_json)

        self._save()

    def _save(self) -> None:
        se = self.helper.driver.find_element(By.ID, 'save_id')
        se.click()
        wait_for_alert(self.helper.driver).accept()

    def _set_position(self, settings: str) -> None:
        field = self.helper.driver.find_element(By.XPATH, '//*[@id="position_css_id"]')

        area = field.find_element(By.CLASS_NAME, 'cm-content')
        area.click()

        # for some reason area.clear() caused
        # selenium.common.exceptions.ElementNotInteractableException: Message: Element <textarea> could not be scrolled into view

        def contents() -> str:
            return self.helper.driver.execute_script('return arguments[0].cmView.view.state.doc.toString()', area)

        # TODO FFS. these don't seem to work??
        # count = len(area.get_attribute('value'))
        # and this only returns visible porition of the text??? so only 700 characters or something
        # count = len(field.text)
        # count += 100  # just in case
        count = 3000  # meh
        # focus ends up at some random position, so need both backspace and delete
        area.send_keys(*([Keys.BACKSPACE] * count + [Keys.DELETE] * count))
        assert contents() == ''
        area.send_keys(settings)

        # just in case, also need to remove spaces to workaround indentation
        assert [l.strip() for l in contents().splitlines()] == [l.strip() for l in settings.splitlines()]

    def _set_endpoint(self, *, host: str | None, port: str | None) -> None:
        # todo rename to 'backend_id'?
        ep = self.helper.driver.find_element(By.ID, 'host_id')
        ep.clear()
        # sanity check -- make sure there are no race conditions with async operations
        assert ep.get_attribute('value') == ''
        if host is None:
            return
        assert port is not None
        ep.send_keys(f'{host}:{port}')
        assert ep.get_attribute('value') == f'{host}:{port}'


# TODO gradually replace TestHelper and other older stuff
@dataclass
class Addon:
    helper: AddonHelper

    @property
    def options_page(self) -> OptionsPage:
        return OptionsPage(helper=self.helper)

    def open_search_page(self, query: str = "") -> None:
        self.helper.open_page('search.html' + query)

        Wait(self.helper.driver, timeout=10).until(
            EC.presence_of_element_located((By.ID, 'visits')),
        )

    @property
    def sidebar(self) -> Sidebar:
        driver = self.helper.driver
        if driver.name == 'chrome':
            browser_version = tuple(map(int, driver.capabilities['browserVersion'].split('.')))
            driver_version = tuple(
                map(int, driver.capabilities['chrome']['chromedriverVersion'].split(' ')[0].split('.'))
            )
            last_working = (113, 0, 5623, 0)
            if browser_version > last_working or driver_version > last_working:
                # NOTE: feel free to comment this out if necessary, it's just to avoid hours of debugging
                raise RuntimeError(
                    f"""
NOTE: you're using chrome {browser_version} with chromedriver {driver_version}.
Some tests aren't working with recent Chrome versions (later than {last_working}) due to regressions in chromedriver.
See https://bugs.chromium.org/p/chromedriver/issues/detail?id=4440
"""
                )
        return Sidebar(addon=self)

    def activate(self) -> None:
        # TODO the activate command could be extracted from manifest too?
        cmd = {
            2: Command.ACTIVATE,
            3: Command.ACTIVATE_V3,  # meh
        }[self.helper.manifest_version]
        self.helper.trigger_command(cmd)

    def mark_visited(self) -> None:
        self.helper.trigger_command(Command.MARK_VISITED)

    def search(self) -> None:
        # cur_window_handles = self.driver.window_handles
        self.helper.trigger_command(Command.SEARCH)
        # self.wait_for_search_tab(cur_window_handles)

    def configure(self, **kwargs) -> None:
        self.options_page.configure_extension(**kwargs)

    def open_context_menu(self) -> None:
        # looks like selenium can't interact with browser context menu...
        assert not self.helper.headless
        driver = self.helper.driver

        chain = ActionChains(driver)
        chain.move_to_element(driver.find_element(By.TAG_NAME, 'h1')).context_click().perform()

        if driver.name == 'chrome':
            offset = 2  # Inspect, View page source
        else:
            offset = 0

        self.helper.gui_write(['up'] + ['up'] * offset + ['enter'], interval=0.5)

    # TODO this doesn't belong to this class really, think about it
    def move_to(self, element) -> None:
        ActionChains(self.helper.driver).move_to_element(element).perform()

    def wait_for_search_tab(self, cur_window_handles) -> None:
        driver = self.helper.driver
        # for some reason the webdriver's context stays the same even when new tab is opened
        # ugh. not sure why it's so elaborate, but that's what stackoverflow suggested
        Wait(driver, timeout=5).until(EC.number_of_windows_to_be(len(cur_window_handles) + 1))
        new_windows = set(driver.window_handles) - set(cur_window_handles)
        assert len(new_windows) == 1, new_windows
        [new_window] = new_windows
        driver.switch_to.window(new_window)
        Wait(driver, timeout=5).until(EC.presence_of_element_located((By.ID, 'promnesia-search')))


@pytest.fixture
def addon(driver: Driver) -> Addon:
    addon_source = get_addon_source(kind=driver.name)
    helper = AddonHelper(driver=driver, addon_source=addon_source)
    return Addon(helper=helper)
