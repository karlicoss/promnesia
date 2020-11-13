/* @flow */

import type {Url, SearchPageParams} from './common';
import {Visits, Blacklisted, unwrap, Methods, ldebug, linfo, lerror, lwarn} from './common'
import {getOptions, setOptions, THIS_BROWSER_TAG} from './options';

import {chromeTabsExecuteScriptAsync, chromeTabsInsertCSS, achrome} from './async_chrome'
import {showTabNotification, defensify, notifications} from './notifications'
import {Blacklist} from './blacklist'
import {isAndroid, allsources} from './sources'

const isMobile = isAndroid;


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


type Result = Visits | Blacklisted | Error

export async function getVisits(url: Url): Promise<Result> {
    const blacklist = await Blacklist.get()
    const bl = await blacklist.contains(url);
    if (bl != null) {
        return new Blacklisted(url, bl);
    }

    return await allsources.visits(url)
}

type IconStyle = {
    icon: string,
    title: string,
    text: string,
};


// TODO this can be tested?
function getIconStyle(result: Result): IconStyle {
    if (result instanceof Blacklisted) {
        return {icon: 'images/ic_blacklisted_48.png', title: `Blacklisted: ${result.reason}`, text: ''}
    }

    // TODO I guess it's kind of 'critical error'?
    // TODO could check if it's a network error
    // then if it's offline, detect it and set a non-error indicator?
    // https://stackoverflow.com/a/42334842/706389
    // but considering 99% of usecases are localhost, doesn't matter
    if (result instanceof Error) {
        return {icon: 'images/ic_error.png'         , title: `ERROR: ${result.message}`, text: ''}
    }

    const [good, errs] = result.partition()

    if (errs.length > 0) {
        return {icon: 'images/ic_error.png'         , title: `${errs.length} errors`, text: errs.map(x => x.toString()).join('\n')}
    }
    // TODO if there are errors, need to mix them in?

    const vcount = good.length
    if (vcount === 0) {
        return {icon: 'images/ic_not_visited_48.png', title: 'No data', text: ''};
    }
    const cp = [];

    // meh.. accessing result after we 'deconstructed' it..
    const self_contexts = result.self_contexts()
    const ccount = self_contexts.length;
    if (ccount > 0) {
        cp.push(`${ccount} contexts`);
    }

    const rcontexts  = result.relative_contexts()
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
        // TODO would be nice to add help aboud these icons somewhere...
        return {icon: 'images/ic_relatives_48.png'    , title: `${vcount} visits, ${ctext}`, text: btext};
    }
    // TODO a bit ugly, but ok for now.. maybe cut off by time?
    const boring = good.every(v => v.tags.length == 1 && v.tags[0] == THIS_BROWSER_TAG)
    if (boring) {
        // TODO not sure if really worth distinguishing..
        return {icon: "images/ic_boring_48.png"     , title: `${vcount} visits (${THIS_BROWSER_TAG} only)`, text: ''};
    } else {
        return {icon: "images/ic_blue_48.png"       , title: `${vcount} visits`, text: ''};
    }
}


async function updateState (tab: chrome$Tab) {
    const url = unwrap(tab.url);
    const tabId = unwrap(tab.id);

    if (ignored(url)) {
        // todo reflect in the sidebar/popup?
        linfo("ignoring %s", url);
        return;
    }

    const opts = await getOptions();
    // TODO this should be executed as an atomic block?

    const inject = () => chromeTabsExecuteScriptAsync(tabId, {file: 'sidebar.js'})
    // TODO hmm. in theory script and CSS injections commute, but css order on the othe hand might matter?
    // not sure, but using deferred promises just in case
          .then(() => chromeTabsInsertCSS(tabId, {file: 'sidebar-outer.css'}))
          .then(() => chromeTabsInsertCSS(tabId, {code: opts.position_css}));


    // NOTE: if the page is unreachable, we can't inject stuff in it
    // not sure how to detect it? tab doesn't have any interesting attributes
    // firefox sets tab.title to "Server Not Found"? (TODO also see isOk logic below)
    // TODO in this case, could set browser action to open a new tab (i.e. search) or something?
    await defensify(inject, `sidebar injection for tabId: ${tabId} url: ${url}`)();
    // TODO crap, at first I forgot () at the end, and flow didn't complain which resulted in flakiness wtf??

    let visits = await getVisits(url)
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
        ].includes(icon); // meh. hacky
        // TODO make dependent on options?
        if (interesting) {
            action.show(tabId);
        } else {
            // not sure if this is really needed, but I feel like it persists otherwise on android
            action.hide(tabId);
        }
    }

    if (visits instanceof Blacklisted) {
        // FIXME not sure if can even happend here??
        return
    }

    if (visits instanceof Error) {
        // meh. but I guess kinda does the trick
        visits = new Visits(url, url, [visits])
    }
    console.assert(visits instanceof Visits)
  
    // right, we can't inject code into error pages (effectively, internal). For these, display popup instead of sidebar?
    // TODO and show system wide notification instead of tab notification?
    // https://stackoverflow.com/questions/32761782/can-a-chrome-extension-run-code-on-a-chrome-error-page-i-e-err-internet-disco
    // https://stackoverflow.com/questions/37093152/unchecked-runtime-lasterror-while-running-tabs-executescript-cannot-access-cont
    // a little hacky, but kinda works? in Firefox too apparently
    const isOk = (await achrome.tabs.get(tabId)).favIconUrl != 'chrome://global/skin/icons/warning.svg'

    // TODO maybe store last time we showed it so it's not that annoying... although I definitely need js popup notification.
    const locs = visits.self_contexts().map(l => l == null ? null : l.title)
    if (locs.length !== 0) {
        const msg = `${locs.length} contexts!\n${locs.join('\n')}`
        if (opts.contexts_popup_on) {
            await showTabNotification(tabId, msg)
        }
    }

    if (isOk) {
        // TODO even compiling this takes 50ms if 10K visits??
        // faster means of communication are going to require
        // so perhaps instead, truncate and suggest to use 'search-like' interface
        chrome.tabs.sendMessage(tabId, {
            method: Methods.BIND_SIDEBAR_VISITS,
            data  : visits.toJObject(),
        })
    } else {
        console.warn("FIXME implement binding visits to popup? or at least show error message")
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
    const results = unwrap(mresults)[0];

    const unique = Array.from(new Set(results));
    const good_urls = unique.filter(u => !is_bad(u));

    const blacklist = await Blacklist.get();
    // TODO ugh. filter can't be async, so we have to do this separately...
    const urls = [];
    for (const u of good_urls) {
        const ur = await blacklist.contains(u);
        if (ur === null) {
            urls.push(u);
        }
    }

    // TODO check if zero? not sure if necessary...
    // TODO maybe, I need a per-site extension?
    const resp = await allsources.visited(urls)
    if (resp instanceof Error) {
        await notifications.error(tabId, resp)
        return
    }

    // TODO ok, we received exactly same elements as in res. now what??
    // TODO cache results internally? At least for visited. ugh.
    // TODO make it custom option?
    const vis = {};
    for (let i = 0; i < urls.length; i++) {
        vis[urls[i]] = resp[i];
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

function ignored(url: string): ?string {
    if ([
        'https://www.google.com/_/chrome/newtab?ie=UTF-8', // ugh, not sure how to fix that properly
        'about:blank', // not sure why about:blank is loading like 5 times.. but this seems to fix it
    ].includes(url)) {
        return 'blank page'
    }

    // TODO might be bad url
    if (isSpecialProtocol(url)) {
        return 'special page'
    }

    return null
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
    if (!url) { /* on Vivaldi I've seen url being "" */
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


export async function getActiveTab(): Promise<?chrome$Tab> {
    const tabs = await achrome.tabs.query({
        currentWindow: true,
        active: true,
    })
    if (tabs.length == 0) {
        return null // might be on special pages..
    }

    if (tabs.length > 1) {
        console.error("Multiple active tabs: %o", tabs) // TODO handle properly?
    }
    const tab = tabs[0]
    return tab
}


type ShouldProcess = {|
    url: string,
    tid: number,
|}

// check if page needs handling and notify suer if/why it can't be processed
async function shouldProcessPage(tab: ?chrome$Tab): Promise<?ShouldProcess> {
    if (tab == null) {
        await notifications.page_ignored(null, null, "Couldn't determine current tab: must be a special page (or a bug?)")
        return
    }
    const url = unwrap(tab.url)
    const tid = unwrap(tab.id)
    let ireason = ignored(url)
    if (ireason != null) {
        await notifications.page_ignored(tid, url, ireason)
        return null
    }
    const blacklist = await Blacklist.get()
    const bl = await blacklist.contains(url)
    // todo let blacklist return Blacklisted object?
    if (bl != null) {
        // TODO show popup; suggest to whitelist?
        await notifications.blacklisted(tid, new Blacklisted(url, bl))
        return null
    }
    return {
        url: url,
        tid: tid,
    }
}

// TODO would be cool to display visited links summary...
async function handleMarkVisited() {
    // TODO actually use mark visited setting?
    // const opts = await getOptions();
    const atab = await getActiveTab()
    let should = await shouldProcessPage(atab)
    if (should == null) {
        return
    }
    let {tid: tid} = should
    await markVisited(tid) // no need to await?
}

async function handleOpenSearch(p: SearchPageParams = {}) {
    const params = new URLSearchParams()
    for (const [k, v] of Object.entries(p)) {
        // $FlowFixMe
        params.append(k, v)
    }
    const ps = params.toString()
    const search_url = chrome.runtime.getURL('search.html') + (ps.length == 0 ? '' : '?' + ps)
    chrome.tabs.create({url: search_url})
    // TODO get current tab url and pass as get parameter?
}


const onMessageCallback = async (msg) => { // TODO not sure if should defensify here?
    const method = msg.method;
    if (method == Methods.GET_SIDEBAR_VISITS) {
        const atab = unwrap(await getActiveTab())
        const url = unwrap(atab.url)
        if (!ignored(url)) { // TODO shouldn't have been requested in the first place? allso pass through shouldHandle?
            const visits = await getVisits(unwrap(atab.url));
            if (visits instanceof Visits) {
                return visits.toJObject()
            } else {
                // hmm. generally shouldn't happen, since sidebar is not bound on blacklisted urls
                // show notification in dev mode?
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
        const utc_timestamp_s: number = msg.utc_timestamp_s
        await handleOpenSearch({
            utc_timestamp_s: utc_timestamp_s.toString()
        })
    } else if (method == Methods.MARK_VISITED) {
        await handleMarkVisited()
    } else if (method == Methods.OPEN_SEARCH) {
        await handleOpenSearch()
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

// note: this is user click callback
export async function injectSidebar(tab: chrome$Tab) {
    const should = await shouldProcessPage(tab)
    if (should == null) {
        return
    }
    const {tid: tid} = should
    await achrome.tabs.executeScript(tid, {file: 'sidebar.js'})
    await achrome.tabs.executeScript(tid, {code: 'toggleSidebar();'})
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
        // TODO throw? // yea probably
        lerror("unexpected command %s", cmd);
    }
}, 'onCommand');


async function blacklist(e): Promise<void> {
    const url = unwrap(e.pageUrl);
    const atab = unwrap(await getActiveTab())  // todo get url from tab?
    const tabId = unwrap(atab.id);

    // TODO I'm really not sure it's the right way to do this..

    let prompt = `Blacklist. Supported formats:
- domain.name, e.g.: web.telegram.org
      Will exclude whole Telegram website.
- http://exact/match, e.g.: http://github.com
      Will only exclude Github main page. Subpages will still work.
- /regul.r.*expression/, e.g.: /github.*/yourusername/
      Quick way to exclude your own Github repostitories.
`;

    const res = await achrome.tabs.executeScript(tabId, {
        code: `prompt(\`${prompt}\`, "${url}");`
    })
    if (res == null) {
        console.info('user chose not to blacklist %s', url);
        return;
    }
    const to_blacklist: string = res[0]

    // TODO not sure if it should be normalised? just rely on regexes, it should be fine 99% of time?
    console.debug('blacklisting %s', to_blacklist);

    const opts = await getOptions();
    opts.blacklist += (opts.blacklist.endsWith('\n') ? '' : '\n') + to_blacklist;

    /*
    TODO ''.split('\n') gives an emptly line, which would block local files
    will fix later if necessary, it's not a big issue I guess
    */
    const ll = opts.blacklist.split(/\n/).length;
    // TODO could open sidebar here and display blacklist??
    await showTabNotification(tabId, `Added ${to_blacklist} to blacklist (${ll} items now)`, 'blue')
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

// TODO maybe this is what needs to be persisted?
var backgroundInitialised = false; // should be synchronous hopefully?
function initBackground() {
    /* better set early to minimize the potential for races? */
    backgroundInitialised = true;

    // $FlowFixMe
    chrome.runtime.onMessage.addListener(onMessageCallback);

    registerActions();

    // TODO make it defensive in case of error tabs? if it fails then can be conservative and ignore menu etc anyway
    isAndroid().then(android => {
        if (android) {
            return;
        }

        //  $FlowFixMe // err, complains at Promise but nevertheless works
        chrome.commands.onCommand.addListener(onCommandCallback);

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

        //  $FlowFixMe // err, complains at Promise but nevertheless works
        chrome.contextMenus.onClicked.addListener(onMenuClickedCallback);
    })
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

    if (backgroundInitialised) {
        console.debug("background already initialised");
        return;
    }

    // TODO elaborate
    if (aurl && isSpecialProtocol(aurl)) {
        lwarn("Suppressing special background page %s", aurl);
        return;
    }

    console.info("Registering background page callbacks in tab %s", aurl);

    /* TODO not sure if ok or not to await? it shouldn't be blocking right? */
    initBackground();
});
