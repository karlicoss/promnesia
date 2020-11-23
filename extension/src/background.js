/* @flow */

import type {Url, SearchPageParams} from './common';
import {Visit, Visits, Blacklisted, unwrap, Methods} from './common'
import type {Options} from './options'
import {Toggles, getOptions, setOption, THIS_BROWSER_TAG} from './options'

import {achrome} from './async_chrome'
import {defensify, notifications, Notify} from './notifications'
import {Filterlist} from './filterlist'
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

type IconStyle = {
    icon: string,
    title: string,
    text: string,
}


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
        console.info("ignoring %s", url)
        return
    }

    const opts = await getOptions()

    // TODO right... so if sidebar isn't injected, the messages will not be delivered.. well, hopefully it's quick enough..
    // also this really needs to happen once for a specific tab? otherwise gonna have callback crap (i.e. messages recieved multiple times)

    // TODO only inject after blacklist check? just in case?
    const inject = () => achrome.tabs.executeScript(tabId, {file: 'sidebar.js'})
    // TODO hmm. in theory script and CSS injections commute, but css order on the othe hand might matter?
    // not sure, but using deferred promises just in case
          .then(() => achrome.tabs.insertCSS(tabId, {file: 'sidebar-outer.css'}))
          .then(() => achrome.tabs.insertCSS(tabId, {file: 'sidebar.css'      }))
          .then(() => achrome.tabs.insertCSS(tabId, {code: opts.position_css  }))


    // NOTE: if the page is unreachable, we can't inject stuff in it
    // not sure how to detect it? tab doesn't have any interesting attributes
    // firefox sets tab.title to "Server Not Found"? (TODO also see isOk logic below)
    // TODO in this case, could set browser action to open a new tab (i.e. search) or something?
    await defensify(inject, `sidebar injection for tabId: ${tabId} url: ${url}`)();
    // TODO crap, at first I forgot () at the end, and flow didn't complain which resulted in flakiness wtf??


    let visits: Result
    const filterlist = await Filterlist.global()
    const bl = await filterlist.contains(url)
    if (bl != null) {
        visits = new Blacklisted(url, bl)
    } else {
        // ok to query
        if (opts.mark_visited_always) {
            setTimeout(() => doToggleMarkVisited(tabId, {show: true})) // run it in parallel
        }
        visits = await allsources.visits(url)
    }

    let {icon, title, text} = getIconStyle(visits)

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
        return
    }

    if (opts.sidebar_always_show) {
        // TODO maybe hide if there are no visits?
        // let it sxecute asynchronously
        setTimeout(() => openSidebar(tab))
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
            await Notify.notify(tabId, msg, {color: 'green'})
        }
    }

    if (isOk) {
        // TODO even compiling this takes 50ms if 10K visits??
        // faster means of communication are going to require
        // so perhaps instead, truncate and suggest to use 'search-like' interface
        sendSidebarMessage(tabId, {
            method: Methods.BIND_SIDEBAR_VISITS,
            data  : visits.toJObject(),
        })
    } else {
        console.warn("TODO implement binding visits to popup? or at least show error message")
    }
}


function sendSidebarMessage(tabId: number, message: any) {
    // ugh.. just so I don't shoot myself in the foot again with using runtime.sendMessage...
    chrome.tabs.sendMessage(tabId, message)
}


async function filter_urls(urls: Array<?Url>) {
    const good: Set<Url> = new Set()
    for (const u of urls) {
        if (u == null || !u.includes('://')) {
            continue
        }
        good.add(u)
    }
    // TODO add smth like blacklist.filter(Iterable)?
    const filterlist = await Filterlist.forMarkVisited()
    const res: Array<Url> = []
    for (const u of good) {
        const ur = await filterlist.contains(u)
        if (ur === null) {
            res.push(u)
        }
    }
    return res
}


async function doToggleMarkVisited(tabId: number, {show}: {show: ?boolean} = {show: null}) {
    // first check if we need to disable TODO
    const _should_show = await achrome.tabs.executeScript(tabId, {
        code: `
{
    let res // ?boolean
    let show = ${show == null ? 'null' : String(show)}
    const shown = window.promnesiaShowsVisits || false
    if (show == null) {
        // we want the opposite
        show = !shown
    }
    if (show === shown) {
        res = null // no change
    } else if (show) {
        res = true // should show
        window.promnesiaShowsVisits = true // ugh. set early to avoid race conditions...
    } else {//
        res = false // should hide
        setTimeout(() => hideMarks()) // async to return straightaway
        window.promnesiaShowsVisits = false
    }
    res
}
`})
    const should_show: ?boolean = unwrap(_should_show)[0]
    if (should_show == null) {
        console.debug('requested state %s: no change needed', show)
        return
    } else if (should_show === false) {
        console.debug('marks were hidden')
        return
    }

    // collect URLS from the page
    const mresults = await achrome.tabs.executeScript(tabId, {
        code: `
     // NOTE: important to make a snapshot here.. otherwise might go in an infinite loop
     link_elements = Array.from(document.getElementsByTagName("a"))
     link_elements.map(el => {
        try {
            // handle relative urls
            return new URL(el.href, document.baseURI).href
        } catch {
            return null
        }
     })
 `
})
    // not sure why it's returning array..
    const results: Array<?Url> = unwrap(mresults)[0]
    const page_urls = Array.from(await filter_urls(results))
    const resp = await allsources.visited(page_urls)
    if (resp instanceof Error) {
        await Notify.error(tabId, resp)
        return
    }

    const visited: Map<Url, Visit> = new Map()
    for (let i = 0; i < page_urls.length; i++) {
        // NOTE: response is guaranteed to have the same length
        let r = resp[i]
        if (r == null) {
            continue
        }
        visited.set(page_urls[i], r)
    }

    // if a link appears on the page too many times,
    // either it's not very importitant, or normalisation is wrong?
    // either way it ends up very spammy on the page.. easy way to check is on something like reddit, or google search page..
    // so let's filter them..
    const THRESHOLD = 10 // todo add to settings?
    const stats: Map<Url, number> = new Map()
    for (const url of results) { // NOTE: traverse over original results, duplicates need to be taken into the account
        if (url == null) {
            continue
        }
        const v = visited.get(url)
        if (v == null) {
            continue
        }
        const nu = v.normalised_url
        stats.set(nu, (stats.get(nu) || 0) + 1)
    }

    for (const url of page_urls) {
        let v = visited.get(url)
        if (v == null) {
            continue
        }
        const stat = stats.get(v.normalised_url) || 0
        if (stat > THRESHOLD) {
            // todo log it somehow?? dunno, might be too spammy
            visited.delete(url)
        }
    }
    // todo ugh. errors inside the script (e.g. syntax errors) get swallowed..
    // TODO not sure.. probably need to inject the script once and then use a message listener or something like in sidebar??
    await achrome.tabs.insertCSS(tabId, {
        file: 'showvisited.css',
    })
    await achrome.tabs.executeScript(tabId, {
        file: 'showvisited.js',
    })
    await achrome.tabs.executeScript(tabId, {
        code: `
visited = new Map(JSON.parse(${JSON.stringify(JSON.stringify([...visited]))}))
setTimeout(() => showMarks())
// best to set it in case of partial processing
window.promnesiaShowsVisits = true
`
    })
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

function ignored(url: ?string): ?string {
    if (url == null) {
        return 'URL not set'
    }
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

// $FlowFixMe
chrome.tabs.onUpdated.addListener(defensify(async (tabId: number, info, tab: chrome$Tab) => {
    // too spammy in logs
    delete tab.favIconUrl
    delete info.favIconUrl
    //
    console.debug('onUpdated %o %o', tab, info)

    const url = tab.url
    const ireason = ignored(url)
    if (ireason != null) {
        /* on Vivaldi I've seen url being "" */
        console.debug('onUpdated %s: ignoring, reason: %s', url, ireason)
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
        return
    }
    console.info('requesting! %s', url)
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
    // TODO ideally only do this once, at the injection site?
    const filterlist = await Filterlist.global()
    const bl = await filterlist.contains(url)
    // todo let blacklist return Blacklisted object?
    if (bl != null) {
        await notifications.excluded(tid, new Blacklisted(url, bl))
        return null
    }
    return {
        url: url,
        tid: tid,
    }
}

// TODO would be cool to display visited links summary...
async function handleToggleMarkVisited() {
    // TODO actually use mark visited setting?
    // const opts = await getOptions();
    const atab = await getActiveTab()
    let should = await shouldProcessPage(atab)
    if (should == null) {
        return
    }
    let {tid: tid} = should
    await doToggleMarkVisited(tid) // no need to await?
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
    const method = msg.method
    if (method == Methods.GET_SIDEBAR_VISITS) {
        // TODO not sure if it might do unnecessary notifications here?
        const atab = await getActiveTab()
        // not sure if can happen.. but just in case
        const should = await shouldProcessPage(atab)
        if (should) {
            const {url: url} = should
            const visits = await allsources.visits(url)
            if (visits instanceof Visits) {
                return visits.toJObject()
            } else {
                // hmm. generally shouldn't happen, since sidebar is not bound on blacklisted urls
                // show notification in dev mode?
                console.trace("Shouldn't have happened! %o", visits)
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
        await defensify(handleToggleMarkVisited, 'handleToggleMarkVisited')()
    } else if (method == Methods.OPEN_SEARCH) {
        await handleOpenSearch()
    } else if (method == Methods.ZAPPER_EXCLUDELIST) {
        await AddToMarkVisitedExcludelist.handleZapperResult(msg)
    }
    return false;
}


/*
   On android, clicking on icon in address bar doesn't seem to work.. however clicking in menu triggers this action?
   https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Differences_between_desktop_and_Android#User_interface

   popup is available for pageAction?? can use it for blacklisting/search?
*/
async function registerActions() {
    // NOTE: on mobile, this sets action for both icon (if it's displayed) and in the menu
    for (const action of (await actions())) {
        // $FlowFixMe
        action.onClicked.addListener(defensify(openSidebar, 'action.onClicked'));
    }
}

// note: this is user click callback
export async function openSidebar(tab: chrome$Tab) {
    const should = await shouldProcessPage(tab)
    if (should == null) {
        return
    }
    const {tid: tid} = should
    // TODO eh, if the user clicks the icon too fast, it might not have a receiver? is there a way to find out??
    sendSidebarMessage(tid, {method: Methods.SIDEBAR_TOGGLE})
}


// NOTE: these have to be in sync with webpack.config.js
// presumably shouldn't rename either otherwise will impact existing user keybindings
const COMMAND_SEARCH       = 'search';
const COMMAND_MARK_VISITED = 'mark_visited';

const onCommandCallback = defensify(async cmd => {
    // todo maybe show a notification or something on command? just to give a sense of progress...
    // ok apparently background page shouldn't communicate with itself via messages. wonder how could it work for me before..
    // https://stackoverflow.com/a/35858654/706389
    if (cmd === COMMAND_MARK_VISITED) {
        await handleToggleMarkVisited() // TODO use message passing? so it's a single point of entry? not sure
    } else if (cmd === COMMAND_SEARCH) {
        await handleOpenSearch()
    } else {
        throw new Error(`unexpected command ${cmd}`)
    }
}, 'onCommand')


type MenuInfo = {
    menuItemId: string,
    linkUrl?: string,
}


async function active(): Promise<TabUrl> {
    const atab = unwrap(await getActiveTab())
    return {
        tabId: unwrap(atab.id ),
        url  : unwrap(atab.url),
    }
}


async function globalExcludelistPrompt(): Promise<Array<Url>> {
    // NOTE: needs to take active tab becaue tab isn't present in the 'info' object if it was clicked from the launcher etc.
    const {tabId: tabId, url: url} = await active()
    let prompt = `Global excludelist. Supported formats:
- domain.name, e.g.: web.telegram.org
      Will exclude whole Telegram website.
- http://exact/match, e.g.: http://github.com
      Will only exclude Github main page. Subpages will still work.
- /regul.r.*expression/, e.g.: /github.*/yourusername/
      Quick way to exclude your own Github repostitories.
`;

    // ugh. won't work for multiple urls, prompt can only be single line...
    const res = await achrome.tabs.executeScript(tabId, {
        code: `prompt(\`${prompt}\`, "${url}");`
    })
    if (res == null || res[0] == null) {
        console.info('user chose not to add %s', url)
        return []
    }
    return [res[0]]
}

async function handleAddToGlobalExcludelist() {
    const added: Array<Url> = await globalExcludelistPrompt()
    if (added.length == 0) {
        return
    }
    const {tabId: tabId, url: _url} = await active()
    // TODO not sure if it should be normalised? just rely on regexes, it should be fine 99% of time?
    console.debug('excluding %o', added)

    const opts = await getOptions()
    let blacklist = opts.blacklist
    blacklist += (blacklist.endsWith('\n') ? '' : '\n') + added.join('\n')
    /*
    TODO ''.split('\n') gives an emptly line, which would block local files
    will fix later if necessary, it's not a big issue I guess
    */
    const ll = blacklist.split(/\n/).length;
    // TODO could open sidebar here and display blacklist??
    await Notify.notify(tabId, `Added ${String(added)} to blacklist (${ll} items now)`, {color: 'blue'})
    await setOption({blacklist: blacklist})
}

type TabUrl = {|
    tabId: number,
    url: string,
|}


const AddToMarkVisitedExcludelist = {
    zapper: async function () {
        // TODO only call prompts if more than one? sort before showing?
        const {tabId: tabId, url: _url} = await active()

        await achrome.tabs.executeScript(tabId, {
            code: `{
let listener = e => {
    e.stopPropagation()

    const tgt = e.target
    const old = tgt.style.outline

    tgt.addEventListener('mouseout', e => {
        tgt.style.outline = old
    })
    // display zapper frame
    tgt.style.outline = '4px solid #07C'
    // todo use css class?
}
document.addEventListener('mouseover', listener)

document.addEventListener('click', e => {
    // console.error("CLiCK!!! %o", e)
    document.removeEventListener('mouseover', listener)

    // FIXME ugh. it also captures file:// links and javascript:
    // should't traverse inside promnesia clases...
    let links = Array.from(e.target.getElementsByTagName('a')).map(el => {
        const href = el.href
        if (href == null) {
            return null
        }
        try {
            // handle relative urls
            return new URL(href, document.baseURI).href
        } catch (e) {
            console.error(e)
            return null
        }
    }).filter(e => e != null)
    links = [...new Set(links)].sort() // make unique
    //
    chrome.runtime.sendMessage({method: '${Methods.ZAPPER_EXCLUDELIST}', data: links})
})
let cancel = e => {
    // console.error("ESCAPE!!!, %o", e)
    if (e.key == 'Escape') {
        document.removeEventListener('mouseover', listener)
        window.removeEventListener('keydown', cancel)
    }
}
window.addEventListener('keydown', cancel)

}`})
    },
    handleZapperResult: async function(msg) {
        const urls: Array<Url> = msg.data
        await AddToMarkVisitedExcludelist.add(urls)
    },
    add: async function(urls: Array<Url>) {
        // TODO filter against existing list first? not sure + global list??
        const {tabId: tabId, url: _tabUrl} = await active()
        if (urls.length > 1) {
            // TODO prompt to filter?
        }

        if (urls.length == 0) {
            await Notify.error(
                tabId,
                'No URLs were detected'
            )
            return
        }

        const opts = await getOptions()
        let cur = opts.mark_visited_excludelist
        // TODO add  comment, i.e. from which website?
        cur += (cur.endsWith('\n') ? '' : '\n') + urls.join('\n')

        // TODO hmm, editing here might be nice in case of garbage in the URL... not sure
        await setOption({mark_visited_excludelist: cur})

        const surl = urls.filter(u => '    ' + u).join('\n')
        await Notify.notify(
            tabId,
    `
Excludelist updated with ${urls.length} URLs.
You should see the change after reloading the page.
If you excluded too many by accident, you can edit excludelist in the extension settings.

${surl}
    `.trim(),
            {
                color: 'green',
                duration_ms: 10 * 1000,
            },
        )
    },
    onMenuClick: async function(info: MenuInfo, _tab: chrome$Tab) {
        const url = unwrap(info.linkUrl)
        await AddToMarkVisitedExcludelist.add([url])
    },
}

// todo would be nice to remove decoration.. but kind of minor..



const DEFAULT_CONTEXTS = ['page', 'browser_action']
type MenuEntry = {
    id: string,
    title: string,
    callback: ?((info: MenuInfo, tab: chrome$Tab) => Promise<void>),
    contexts?: Array<chrome$ContextType>, // NOTE: not present interpreted as DEFAULT_CONTEXTS
    parentId?: string,
}


const MENUS: Array<MenuEntry> = [
    {
        id      : 'menu_exclude_mark_visited',
        title   : 'Promnesia: do not mark this link',
        callback: AddToMarkVisitedExcludelist.onMenuClick,
        contexts: ['link'],
    },
    {
        id      : 'menu_global_excludelist',
        title   : "Exclude globally (domain/specific page/subpages)",
        callback: handleAddToGlobalExcludelist,
    },
    {
        id      : 'menu_mark_visited_excludelist',
        title   : "Exclude multiple links from 'mark as visited' (element zapper)",
        callback: AddToMarkVisitedExcludelist.zapper,
    },
    {
        id      : 'menu_mark_visited',
        title   : "Mark/unmark visited urls",
        callback: handleToggleMarkVisited,
    },
    {
        id      : 'menu_search',
        title   : "Search in browsing history",
        callback: (_info, _tab) => handleOpenSearch(),
    },
    {
        id      : 'menu_toggles',
        title   : 'Quick toggles',
        callback: null,
    },
]

type MenuToggle = MenuEntry & {
    checker: (opts: Options) => boolean,
}

const TOGGLES: Array<MenuToggle> = [
    {
        parentId: 'menu_toggles', // meh
        id      : 'menu_toggles_sidebar',
        title   : 'Always show sidebar',
        checker : opts => opts.sidebar_always_show,
        callback: Toggles.showSidebar,
    },
    {
        parentId: 'menu_toggles', // meh
        id      : 'menu_toggles_visited',
        title   : 'Always mark visited links',
        checker : opts => opts.mark_visited_always,
        callback: Toggles.markVisited,
    },
    {
        parentId: 'menu_toggles', // meh
        id      : 'menu_toggles_highlights',
        title   : 'Always show highlights',
        checker : opts => opts.highlight_on,
        callback: Toggles.showHighlights,
    },
]

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
        for (const {id: id, title: title, parentId: parentId, contexts: contexts} of MENUS) {
            chrome.contextMenus.create({
                id: id,
                parentId: parentId,
                title: title,
                contexts: contexts || DEFAULT_CONTEXTS,
            })
        }
        setTimeout(() => getOptions().then((opts) => {
            for (const {id: id, title: title, parentId: parentId, checker: checker, contexts: contexts} of TOGGLES) {
                chrome.contextMenus.create({
                    id: id,
                    parentId: parentId,
                    title: title,
                    contexts: contexts || DEFAULT_CONTEXTS,
                    type: 'checkbox',
                    checked: checker(opts),
                })
            }
        }))

        const onMenuClickedCallback = defensify(async (info: MenuInfo, tab: chrome$Tab) => {
            const mid = info.menuItemId
            for (const m of [...MENUS, ...TOGGLES]) {
                if (mid == m.id) {
                    const cb = m.callback
                    if (cb != null) {
                        await cb(info, tab)
                    }
                    break
                }
            }
        }, 'onMenuClicked');

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
        console.warn("Suppressing special background page %s", aurl)
        return;
    }

    console.info("Registering background page callbacks in tab %s", aurl);

    /* TODO not sure if ok or not to await? it shouldn't be blocking right? */
    initBackground();
});
