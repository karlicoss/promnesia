/* @flow */

import type {Locator, Src, Url, Second, JsonArray, JsonObject} from './common';
import {Visit, Visits, Blacklisted, unwrap, Methods, ldebug, linfo, lerror, lwarn} from './common';
import {get_options_async, setOptions} from './options';
import {chromeTabsExecuteScriptAsync, chromeTabsInsertCSS, chromeTabsQueryAsync, chromeRuntimeGetPlatformInfo, chromeTabsGet} from './async_chrome';
import {showTabNotification, showBlackListedNotification, showIgnoredNotification, defensify, notify} from './notifications';
import {Blacklist} from './blacklist';

async function isAndroid() {
    try {
        const platform = await chromeRuntimeGetPlatformInfo();
        return platform.os === 'android';
    } catch (error) {
        // defensive just in case since isAndroid is kinda crucial for extension functioning
        console.error('error while determining platfrom; assuming not android: %o', error);
        return false;
    }
}

const isMobile = isAndroid; // TODO deprecate old name? note sure

// TODO ugh. en-GB etc can't be parsed by Date.parse afterwards...

// TODO allow to configure in options/or even use local tz
const systemTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
const tz_fmt = new Intl.DateTimeFormat('sv-SE', {
    timeZone: systemTz,
    day   : 'numeric',
    month : 'numeric',
    year  : 'numeric',
    hour  : 'numeric',
    minute: 'numeric',
    second: 'numeric',
});

function normTz(dt: Date): Date {
    // TODO ugh, merge for dt_formatter??
    return new Date(tz_fmt.format(dt));
}


async function actions(): Promise<Array<chrome$browserAction | chrome$pageAction>> {
    const res = [chrome.browserAction];

    const android = await isAndroid();
    if (android) {
        res.push(chrome.pageAction);
    }
    // eh, on mobile neither pageAction nor browserAction have setIcon
    // but we can use pageAction to show at least some (default) icon in some circumstances

    // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Differences_between_desktop_and_Android#User_interface
    return res;
}



function rawToVisits(vis: JsonObject): Visits {
    // TODO filter errors? not sure.
    const visits = vis['visits'].map(v => {
        const dts = v['dt'];
        const dt: Date = normTz(new Date(dts));
        const vtags: Array<Src> = [v['src']]; // TODO hmm. shouldn't be array?
        const vourl: string = v['original_url'];
        const vnurl: string = v['normalised_url'];
        const vctx: ?string = v['context'];
        const vloc: ?Locator = v['locator']
        const vdur: ?Second = v['duration'];
        return new Visit(vourl, vnurl, dt, vtags, vctx, vloc, vdur);
    });
    return new Visits(
        vis['original_url'],
        vis['normalised_url'],
        visits
    );
}


async function queryBackendCommon<R>(params, endp: string): Promise<R> {
    const opts = await get_options_async();
    const endpoint = `${opts.host}/${endp}`;
    // TODO cors mode?
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type' : 'application/json',
            'Authorization': "Basic " + btoa(opts.token),
        },
        body: JSON.stringify(params)
    }).then(response => {
        // right, fetch API doesn't reject on HTTP error status...
        const ok = response.ok;
        if (!ok) {
            throw response.statusText; // TODO...
        }
        return response.json();
    });
    return response;
}

async function getBackendVisits(u: Url): Promise<Visits> {
    return queryBackendCommon<JsonObject>({url: u}, 'visits').then(rawToVisits);
}


// TODO include browser visits here too?
export async function searchVisits(u: Url): Promise<Visits> {
    return queryBackendCommon<JsonObject>({url: u}, 'search').then(rawToVisits);
}

export async function searchAround(timestamp: number): Promise<Visits> {
    return queryBackendCommon<JsonObject>({timestamp: timestamp}, 'search_around').then(rawToVisits);
}

function getDelayMs(/*url*/) {
    return 10 * 1000;
}

const LOCAL_TAG = 'local';


async function getChromeVisits(url: Url): Promise<Visits> {
    const android = await isAndroid();
    if (android) {
        // ugh. 'history' api is not supported on mobile (TODO mention that in readme)
        // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Differences_between_desktop_and_Android#Other_UI_related_API_and_manifest.json_key_differences
        return new Visits(url, url, []);
    }

    // $FlowFixMe
    const results = await new Promise((cb) => chrome.history.getVisits({url: url}, cb));

    // without delay you will always be seeing website as visited
    // TODO but could be a good idea to make it configurable; e.g. sometimes we do want to know immediately. so could do domain-based delay or something like that?
    const delay = getDelayMs();
    const current = normTz(new Date());

    // NOTE: visitTime returns UTC epoch
    const times: Array<Date> = results.map(r => normTz(new Date(r['visitTime']))).filter(dt => current - dt > delay);
    // TODO not sure if need to normalise..
    const visits = times.map(t => new Visit(url, url, t, [LOCAL_TAG]));
    return new Visits(url, url, visits);
}


// TODO think about caching blacklist on background page?
// although need to be careful and invalidate it. ugh.

// TODO ugh. can't keep get_options_async in blacklist.js because jest complains..
async function Blacklist_get(): Promise<Blacklist> {
    const opts = await get_options_async();
    return new Blacklist(opts.blacklist);
}


type Result = Visits | Blacklisted | Error;

export async function getVisits(url: Url): Promise<Result> {
    const blacklist = await Blacklist_get();
    const bl = await blacklist.contains(url);
    if (bl != null) {
        return new Blacklisted(url, bl);
    }
    // TODO hmm. maybe have a special 'error' visit so we could just merge visits here?
    // it's gona be a mess though..
    const backendRes: Visits | Error = await getBackendVisits(url)
          .catch((err: Error) => err);
    if (backendRes instanceof Error) {
        return backendRes;
    }

    const backendVisits = backendRes;
    // NOTE sort of a problem with chrome visits that they don't respect normalisation.. not sure if there is much to do with it
    const chromeVisits = await getChromeVisits(url);
    const allVisits = backendVisits.visits.concat(chromeVisits.visits);
    return new Visits(
        backendVisits.original_url,
        backendVisits.normalised_url,
        allVisits
    );
}

type IconStyle = {
    icon: string,
    title: string,
    text: string,
};


// TODO this can be tested?
function getIconStyle(visits: Result): IconStyle {
    if (visits instanceof Blacklisted) {
        return {icon: 'images/ic_blacklisted_48.png', title: `Blacklisted: ${visits.reason}`, text: ''};
    }

    if (visits instanceof Error) {
        return {icon: 'images/ic_error.png'         , title: `ERROR: ${visits.message}`, text: ''};
    }

    const vcount = visits.visits.length;
    if (vcount === 0) {
        return {icon: 'images/ic_not_visited_48.png', title: 'Not visited', text: ''};
    }
    const cp = [];

    const self_contexts = visits.self_contexts();
    const ccount = self_contexts.length;
    if (ccount > 0) {
        cp.push(`${ccount} contexts`);
    }

    const rcontexts  = visits.relative_contexts();
    const rcount = rcontexts.length;
    if (rcount > 0) {
        // TODO rename to relative later?
        cp.push(`${rcount} child contexts`);
    }

    const btext = rcount == 0 ? `${ccount}` : `${ccount}/${rcount}`;
    const ctext = cp.join(', ');
    if (ccount > 0) {
        return {icon: 'images/ic_visited_48.png'    , title: `${vcount} visits, ${ctext}`, text: btext};
    }
    if (rcount > 0) {
        return {icon: 'images/ic_relatives_48.png'    , title: `${vcount} visits, ${ctext}`, text: btext};
    }
    // TODO a bit ugly, but ok for now.. maybe cut off by time?
    const boring = visits.visits.every(v => v.tags.length == 1 && v.tags[0] == LOCAL_TAG);
    if (boring) {
        // TODO not sure if really worth distinguishing..
        return {icon: "images/ic_boring_48.png"     , title: `${vcount} visits (local only)`, text: ''};
    } else {
        return {icon: "images/ic_blue_48.png"       , title: `${vcount} visits`, text: ''};
    }
}


async function updateState (tab: chrome$Tab) {
    const url = unwrap(tab.url);
    const tabId = unwrap(tab.id);

    if (ignored(url)) {
        linfo("ignoring %s", url);
        return;
    }

    const opts = await get_options_async();
    // TODO this should be executed as an atomic block?

    const inject = () => chromeTabsExecuteScriptAsync(tabId, {file: 'sidebar.js'})
    // TODO hmm. in theory script and CSS injections commute, but css order on the othe hand might matter?
    // not sure, but using deferred promises just in case
          .then(() => chromeTabsInsertCSS(tabId, {file: 'sidebar-outer.css'}))
          .then(() => chromeTabsInsertCSS(tabId, {code: opts.position_css}));


    // NOTE: if the page is unreachable, we can't inject stuf in it
    // not sure how to detect it? tab doesn't have any interesting attributes
    // firefox sets tab.title to "Server Not Found"? (TODO also see isOk logic below)
    // TODO in this case, could set browser action to open a new tab (i.e. search) or something?
    await defensify(inject, 'sidebar injection')();
    // TODO crap, at first I forgot () at the end, and flow didn't complain which resulted in flakiness wtf??

    const visits = await getVisits(url);
    let {icon, title, text} = getIconStyle(visits);

    // TODO move to getIconStyle??
    if (visits instanceof Visits) {
        title = `${title}\nCanonical: ${visits.normalised_url}`;
    }

    // ugh, many of these are not supported on android.. https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/pageAction
    // TODO not sure if can benefit from setPopup?
    for (const action of (await actions())) {
        // ugh, some of these only present in browserAction..
        if (action.setTitle) {
            // $FlowFixMe
             action.setTitle({
                 tabId: tabId,
                 title: title,
             });
        }

        if (action.setIcon) {
            // $FlowFixMe
            action.setIcon({
                tabId: tabId,
                path: icon,
            });
        }
        if (action.setBadgeText) {
            // $FlowFixMe
            action.setBadgeText({
                tabId: tabId,
                text: text,
            });
        }
    }

    /* NOTE: few things here
     * 1. browser action is only shown in the 'settings on android' (and no icon), so we're using page action
     * 2. page action icon can't be changed on android, so we're only showing it when there are contexts
     *    otherwise, we're relying on 'mobile_sidebar_injector' to open the sidebar
     */
    if (await isMobile()) {
        const action = chrome.pageAction;
        const interesting = [
            'images/ic_visited_48.png',
            'images/ic_relatives_48.png',
        ].includes(icon); // FIXME meh. hacky
        // TODO make dependent on options?
        if (interesting) {
            action.show(tabId);
        } else {
            // not sure if this is really needed, but I feel like it persists otherwise on android
            action.hide(tabId);
        }
    }

    // TODO ok, could bind blacklist here as well.. but later
    // TODO wonder if I can do exhaustive check?
    if (visits instanceof Error) {
        // TODO share code with the Visits branch
        await chromeTabsExecuteScriptAsync(tabId, {
            code: `bindError("${visits.message}")`
        });
    } else if (visits instanceof Visits) {
        // right, we can't inject code into error pages (effectively, internal). For these, display popup instead of sidebar?
        // TODO and show system wide notification instead of tab notification?
        // https://stackoverflow.com/questions/32761782/can-a-chrome-extension-run-code-on-a-chrome-error-page-i-e-err-internet-disco
        // https://stackoverflow.com/questions/37093152/unchecked-runtime-lasterror-while-running-tabs-executescript-cannot-access-cont
        // a little hacky, but kinda works? in Firefox too apparently
        const isOk = (await chromeTabsGet(tabId)).favIconUrl != 'chrome://global/skin/icons/warning.svg';

        // TODO maybe store last time we showed it so it's not that annoying... although I definitely need js popup notification.
        const locs = visits.self_contexts().map(l => l == null ? null : l.title);
        if (locs.length !== 0) {
            const msg = `${locs.length} contexts!\n${locs.join('\n')}`;
            if (opts.contexts_popup_on) {
                await showTabNotification(tabId, msg);
            }
        }

        if (isOk) {
            // TODO even compiling this takes 50ms if 10K visits??
            // faster means of communication are going to require
            // so perhaps instead, truncate and suggest to use 'search-like' interface
            await chromeTabsExecuteScriptAsync(tabId, {
                code: `bindSidebarData(${JSON.stringify(visits)})`
            });
        } else {
            console.warn("TODO implement binding visits to popup?");
        }
    }
}


// todo ugh. this can be tested on some static page... I guess?
async function markVisited(tabId) {
    const mresults = await chromeTabsExecuteScriptAsync(tabId, {
        code: `
     link_elements = document.getElementsByTagName("a");
     Array.from(link_elements).map(el => el.href)
 `
});
    function is_bad(u: ?string): boolean {
        if (u == null) {
            return true;
        }
        return u === '#' || u.startsWith('javascript:');
    }
    // not sure why it's returning array..
    const results = unwrap(mresults[0]);

    const unique = Array.from(new Set(results));
    const good_urls = unique.filter(u => !is_bad(u));

    const blacklist = await Blacklist_get();
    // TODO ugh. filter can't be async, so we have to do this separately...
    const res = [];
    for (const u of good_urls) {
        const ur = await blacklist.contains(u);
        if (ur === null) {
            res.push(u);
        }
    }

    // TODO check if zero? not sure if necessary...
    // TODO maybe, I need a per-site extension?
    const resp = await queryBackendCommon<JsonArray>({
        urls: res,
    }, 'visited');

    // TODO ok, we received exactly same elements as in res. now what??
    // TODO cache results internally? At least for visited. ugh.
    // TODO make it custom option?
    const vis = {};
    for (var i = 0; i < res.length; i++) {
        vis[res[i]] = resp[i];
    }
    // TODO make a map from it..
    // TODO use CSS from settings?
    // TODO document how it can be configured
    await chromeTabsInsertCSS(tabId, {
        code: `
.promnesia-visited:after {
  content: "⚫";
  color: #FF4500;
  vertical-align: super;
  font-size: smaller;

  /* prevent selecting along with the text */
  user-select: none;

  position:absolute;
  z-index:100;
}
`
    });
    await chromeTabsExecuteScriptAsync(tabId, {
        code: `
vis = ${JSON.stringify(vis)}; // madness!
{
for (var i = 0; i < link_elements.length; i++) {
    const a_tag = link_elements[i];
    let url = a_tag.href;
    if (url == null) {
        continue;
    }
    if (vis[url] === true) {
        // console.log("adding class to ", a_tag);
        a_tag.classList.add('promnesia-visited');
    }
}
}
`
    });
}

// ok, looks like this one was excessive..
// chrome.tabs.onActivated.addListener(updateState);

function isSpecialProtocol(url: string): boolean {
    // TODO eh, maybe makes more sense to only allow http[s]/ftp/file?
    const pro = new URL(url).protocol;
    if ([
        'chrome:',
        'chrome-devtools:',
        'chrome-extension:',
        'moz-extension:',
        'about:', // e.g. about:addons or about:devtool
    ].includes(pro)) {
        return true;
    }
    return false;
}

function ignored(url: string): boolean {
    if ([
        'https://www.google.com/_/chrome/newtab?ie=UTF-8', // ugh, not sure how to dix that properly
        'about:blank', // not sure why about:blank is loading like 5 times.. but this seems to fix it
    ].includes(url)) {
        return true;
    }

    if (isSpecialProtocol(url)) {
        return true;
    }

    return false;
}

/*
// TODO ehh... not even sure that this is correct thing to do...
// $FlowFixMe
chrome.webNavigation.onDOMContentLoaded.addListener(detail => {
    get_options(opts => {
        if (!opts.dots) {
            return;
        }
        const url = unwrap(detail.url);
        if (detail.frameId != 0) {
            ldebug('ignoring child iframe for %s', url);
            return;
        }

        if (ignored(url)) {
            ldebug("ignoring %s", url);
            return;
        }
        // https://kk.org/thetechnium/
        ldebug('finished loading DOM %s', detail);

        markVisited(detail.tabId, opts);
        // updateState();
    });
});
*/

// chrome.tabs.onReplaced.addListener(updateState);

chrome.tabs.onCreated.addListener((tab) => {
    ldebug("onCreated %s", tab);
});


// $FlowFixMe
chrome.tabs.onUpdated.addListener(defensify(async (tabId, info, tab) => {
    // too spammy in logs
    delete tab.favIconUrl;
    delete info.favIconUrl;
    //
    ldebug("onUpdated %s %s", tab, info);

    const url = tab.url;
    if (url == null) {
        ldebug('onUpdated: ignoring as URL is not set');
        return;
    }

    // TODO make logging optional? not sure if there are any downsides
    if (ignored(url)) {
        linfo('onUpdated: ignored explicitly %s', url);
        return;
    }
    // right, tab updated triggered quite a lot, e.g. when the title is blinking
    // ok, so far there are basically two cases
    // 1. you open new tab. in that case 'url' won't be passed but onDomContentLoaded will be triggered
    // 2. you navigate within the same tab, e.g. on youtube. then url will be passed, but onDomContentLoaded doesn't trigger. TODO not sure if it's always the case. maybe it's only YT
    // TODO shit, so we might need to hide previous dots? ugh...

    // TODO vvvv these might need to be cleaned up; not sure how relevant...
    // page refresh: loading -> complete (no url at any point)
    // clicking on link: loading (url) -> complete
    // opening new link: loading -> loading (url) -> complete
    // ugh. looks like 'complete' is the most realiable???
    // but, I checked with 'complete' and sometimes it would reload many things with loading -> complete..... shit.

    // also if you, say, go to web.telegram.org it's gonna show multiple notifications due to redirect... but perhaps this can just be suppressed..

    if (info['status'] != 'complete') {
        return;
    }
    linfo('requesting! %s', url);
    try {
        await updateState(tab);
    } catch (error) {
        const message = error.message;
        if (message == null) {
            throw error;
        }

        if (message.includes('Invalid tab ID')) {
            console.warn('Error %o ignored; most likely due to closed tab', error);
            return;
        }
        if (message.includes('An unexpected error occurred')) {
            console.warn('Error %o ignored; presumably bug in Firefox https://bugzilla.mozilla.org/show_bug.cgi?id=1397667', error);
            // also that https://bugzilla.mozilla.org/show_bug.cgi?id=1290016
            return;
        }
        throw error;
    }
}, 'onUpdated'));


export async function getActiveTab(): Promise<chrome$Tab> {
    const tabs = await chromeTabsQueryAsync({
        'currentWindow': true,
        'active': true,
    });
    // TODO can it be empty at all??
    if (tabs.length > 1) {
        console.error("Multiple active tabs: %o", tabs); // TODO handle properly?
    }
    const tab = tabs[0];
    return tab;
}

async function showActiveTabNotification(text: string, color: string): Promise<void> {
    const atab = await getActiveTab();
    await showTabNotification(unwrap(atab.id), text, color);
}

async function handleMarkVisited() {
    // TODO actually use mark visited setting?
    // const opts = await get_options_async();
    const atab = await getActiveTab();
    const url = unwrap(atab.url);
    const tid = unwrap(atab.id);
    if (ignored(url)) {
        await showIgnoredNotification(tid, url);
    } else {
        const blacklist = await Blacklist_get();
        const bl = await blacklist.contains(url);
        if (bl != null) {
            await showBlackListedNotification(tid, new Blacklisted(url, bl));
        } else {
            await markVisited(tid);
        }
    }
}

async function handleOpenSearch() {
    // TODO get current tab url and pass as get parameter?
    chrome.tabs.create({ url: "search.html" });
}


const onMessageCallback = async (msg) => { // TODO not sure if should defensify here?
    const method = msg.method;
    if (method == Methods.GET_SIDEBAR_VISITS) {
        const atab = await getActiveTab();
        const url = unwrap(atab.url);
        if (!ignored(url)) { // TODO shouldn't have been requested in the first place?
            const visits = await getVisits(unwrap(atab.url));
            if (visits instanceof Visits) {
                return visits;
            } else {
                // hmm. generally shouldn't happen, since sidebar is not bound on blacklisted urls
                lerror("Shouldn't have happened! %s", visits);
            }
        }
        // TODO err. not sure what's happening here...
        // if i'm using await in return type, it expects me to return visits instead of true/false??
        // is it automatically detecting whether it's a promise or not??
        // perhaps async automatically uncurries last argument?
        // could be Firefox only?
        // sendResponse(visits);
        // return true; // this is important!! otherwise message will not be sent?
    } else if (method == Methods.SEARCH_VISITS_AROUND) {
        // TODO reuse handleOpenSearch?
        const utc_timestamp_s: number = msg.utc_timestamp_s;
        const params = new URLSearchParams();
        params.append('utc_timestamp', utc_timestamp_s.toString());
        const search_url = chrome.extension.getURL('search.html') + '?' + params.toString();
        chrome.tabs.create({'url': search_url});
    } else if (method == Methods.MARK_VISITED) {
        await handleMarkVisited();
    } else if (method == Methods.OPEN_SEARCH) {
        await handleOpenSearch();
    }
    return false;
};


/*
   On android, clicking on icon in address bar doesn't seem to work.. however clicking in menu triggers this action?
   https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Differences_between_desktop_and_Android#User_interface

   popup is available for pageAction?? can use it for blacklisting/search?
*/
async function registerActions() {
    // NOTE: on mobile, this sets action for both icon (if it's displayed) and in the menu
    for (const action of (await actions())) {
        // $FlowFixMe
        action.onClicked.addListener(defensify(injectSidebar, 'action.onClicked'));
    }
}

export async function injectSidebar(tab: chrome$Tab) {
    const url = unwrap(tab.url);
    const tid = unwrap(tab.id);
    if (ignored(url)) {
        // TODO tab notification?
        notify(`${url} can't be handled`);
        return;
    }
    const blacklist = await Blacklist_get();
    const bl = await blacklist.contains(url);
    if (bl != null) {
        await showBlackListedNotification(tid, new Blacklisted(url, bl));
        // TODO show popup; suggest to whitelist?
    } else {
        // TODO ugh. messy
        await chromeTabsExecuteScriptAsync(tid, {file: 'sidebar.js'});
        await chromeTabsExecuteScriptAsync(tid, {code: 'toggleSidebar();'});
    }
}


// TODO reuse these in webpack config...
const COMMAND_SEARCH       = 'search';
const COMMAND_MARK_VISITED = 'mark_visited';

const onCommandCallback = defensify(async cmd => {
    // ok apparently background page shouldn't communicate with itself via messages. wonder how could it work for me before..
    // https://stackoverflow.com/a/35858654/706389
    if (cmd === COMMAND_MARK_VISITED) {
        await handleMarkVisited();
    } else if (cmd === COMMAND_SEARCH) {
        await handleOpenSearch();
    } else {
        // TODO throw?
        lerror("unexpected command %s", cmd);
    }
}, 'onCommand');


async function blacklist(e): Promise<void> {
    const url = unwrap(e.pageUrl);
    const atab = await getActiveTab();
    const tabId = unwrap(atab.id);

    // TODO I'm really not sure it's the right way to do this..

    let prompt = `Blacklist. Supported formats:
- domain.name, e.g.: web.telegram.org
  Will exclude whole Telegram website.
- http://exact/match, e.g.: http://github.com
  Will only exclude Github main page. Subpages will still work.
- /regul.r.*expression/, e.g.: /github.*/username/
  Quick way to exclude your own Github repostitories.
`;

    const to_blacklist = await chromeTabsExecuteScriptAsync(tabId, {
        code: `prompt(\`${prompt}\`, "${url}");`
    });
    if (to_blacklist == null) {
        console.info('user chose not to blacklist %s', url);
        return;
    }

    // TODO not sure if it should be normalised? just rely on regexes, it should be fine 99% of time?
    console.debug('blacklisting %s', to_blacklist);

    const opts = await get_options_async();
    opts.blacklist += (opts.blacklist.endsWith('\n') ? '' : '\n') + to_blacklist;

    /*
    TODO ''.split('\n') gives an emptly line, which would block local files
    will fix later if necessary, it's not a big issue I guess
    */
    const ll = opts.blacklist.split(/\n/).length;
    // TODO could open sidebar here and display blacklist??
    await showActiveTabNotification(`Added ${to_blacklist} to blacklist (${ll} items now)`, 'blue');
    await setOptions(opts);
}


const MENU_BLACKLIST   = 'menu_blacklist';
const MENU_MARK_VISITS = 'menu_mark_visits';
const MENU_SEARCH      = 'menu_search'


// looks like onClicked is more portable...
const onMenuClickedCallback = defensify(async (info) => {
    const mid = info.menuItemId;
    if (       mid === MENU_BLACKLIST) {
        await blacklist(info);
    } else if (mid === MENU_MARK_VISITS) {
        await handleMarkVisited();
    } else if (mid === MENU_SEARCH) {
        await handleOpenSearch();
    }
}, 'onMenuClicked');


/*
  Right, that's a hack for some nasty bug/behaviour that happens both in firefox and chrome.
  Basically, if you have tabs open for html pages within the extensions (e.g. moz-extensions://<id>/search.html ), each of them ends up with a copy of background page.
  That results it multiple responses for commands, messages etc.
  Only relevantinformation I could found about that is https://stackoverflow.com/questions/30856001/why-does-chrome-tabs-create-create-2-tabs , but that didn't really help
  This behaviour is tested by test_duplicate_background_pages to prevent regressions
*/
var backgroundInitialised = false; // should be synchronous hopefully?
async function initBackground() {
    // TODO make it defensive in case of error tabs? if it fails then can be conservative and ignore menu etc anyway
    const android = await isAndroid();

    // $FlowFixMe
    chrome.runtime.onMessage.addListener(onMessageCallback);

    if (!android) {
        // $FlowFixMe // err, complains at Promise but nevertheless works
        chrome.commands.onCommand.addListener(onCommandCallback);
    }

    if (!android) {
        // TODO?? Unchecked runtime.lastError: Cannot create item with duplicate id blacklist-domain on Chrome
        chrome.contextMenus.create({
            'id'       : MENU_BLACKLIST,
            'contexts' : ['page', 'browser_action'],
            'title'    : "Blacklist (domain/specific page/subpages)",
        });
        chrome.contextMenus.create({
            'id'       : MENU_MARK_VISITS,
            'contexts' : ['page', 'browser_action'],
            'title'    : "Mark visited urls",
        });
        chrome.contextMenus.create({
            'id'       : MENU_SEARCH,
            'contexts' : ['page', 'browser_action'],
            'title'    : "Search in browsing history",
        })
    }

    if (!android) {
        // $FlowFixMe // err, complains at Promise but nevertheless works
        chrome.contextMenus.onClicked.addListener(onMenuClickedCallback);
    }

    await registerActions();
    backgroundInitialised = true;
}


/*
  The idea is that each page pokes background.
  If background happens to be extensions' background, it's ignored; otherwise we're trying to register callbacks.
 */
chrome.runtime.onMessage.addListener((info: any, sender: chrome$MessageSender) => {
    if (info.method != "INJECT_BACKGROUND_CALLBACKS") {
        console.debug("ignoring %o %o; %s", info, sender, backgroundInitialised);
        return;
    }
    console.log("onmessage %o %o", info, sender);
    const aurl = sender.tab == null ? null : sender.tab.url;
    if (aurl != null && isSpecialProtocol(aurl)) {
        lwarn("Suppressing special background page %s", aurl);
        return;
    }
    console.info("Registering background page callbacks %s", aurl);
    if (backgroundInitialised) {
        console.debug("background already initialised");
        return;
    }
    initBackground();
});
