/* @flow */

import type {Locator, Tag, Url, Second} from './common';
import {Visit, Visits, Blacklisted, unwrap, Methods} from './common';
import {normaliseHostname} from './normalise';
import type {Options} from './options';
import {get_options_async, setOptions} from './options';
// $FlowFixMe
import reqwest from 'reqwest';

const ACTIONS: Array<chrome$browserAction | chrome$pageAction> = [chrome.browserAction, chrome.pageAction]; // TODO dispatch depending on android/desktop?

// TODO common?
export function showNotification(text: string, priority: number=0) {
    chrome.notifications.create({
        'type': "basic",
        'title': "wereyouhere",
        'message': text,
        'priority': priority,
        'iconUrl': 'images/ic_not_visited_48.png',
    });
}

export function showTabNotification(tabId: number, text: string, color: string='green') {
    // TODO can it be remote script?
    text = text.replace(/\n/g, "\\n"); // ....

    chrome.tabs.executeScript(tabId, {file: 'toastify.js'}, () => {
        chrome.tabs.insertCSS(tabId, {file: 'toastify.css'}, () => {
            chrome.tabs.executeScript(tabId, { code: `
Toastify({
  text: "${text}",
  duration: 2000,
  newWindow: true,
  close: true,
  gravity: "top",
  positionLeft: false,
  backgroundColor: "${color}",
}).showToast();
    `    });
      });
    });
}

function showIgnoredNotification(tabId: number, url: Url) {
    showTabNotification(tabId, `${url} is ignored`, 'red');
}

function showBlackListedNotification(tabId: number, b: Blacklisted) {
    showTabNotification(tabId, `${b.url} is blacklisted: ${b.reason}`, 'red');
}

function rawToVisits(vis): Visits {
    // TODO not sure, maybe we want to distinguish these situations..
    if (vis == null) {
        return new Visits([]);
    }

    // TODO filter errors? not sure.
    return new Visits(vis.map(v => {
        // TODO wonder if server is returning utc...
        // TODO server should return tz aware, probably...
        const dts = v['dt'] + ' UTC'; // jeez. seems like it's the easiest way...

        const dt: Date = new Date(dts);
        const vtags: Array<Tag> = v['tags']; // TODO hmm. backend is responsible for tag merging?
        const vourl: string = v['original_url'];
        const vnurl: string = v['normalised_url'];
        const vctx: ?string = v['context'];
        const vloc: ?Locator = v['locator']
        const vdur: ?Second = v['duration'];
        return new Visit(vourl, vnurl, dt, vtags, vctx, vloc, vdur);
    }));
}

// $FlowFixMe
function log() {
    const args = [];
    for (var i = 1; i < arguments.length; i++) {
        const arg = arguments[i];
        args.push(JSON.stringify(arg));
    }
    console.log('[background] ' + arguments[0], ...args);
}

const ldebug = log; // TODO
const linfo = log; // TODO
// eslint-disable-next-line no-unused-vars
const lerror = log; // TODO

// TODO definitely need to use something very lightweight for json requests..

function queryBackendCommon(params, opts: Options, endp: string, cb: (Visits) => void) {
    const data = JSON.stringify(params);

    const request = new XMLHttpRequest(); // TODO FIXME use reqwest?

    const endpoint = `${opts.host}/${endp}`;
    request.open('POST', endpoint, true);
    request.setRequestHeader('Authorization', `Basic ${btoa(opts.token)}`);
    request.onreadystatechange = () => {
        if (request.readyState != request.DONE) {
            return;
        }
        const status = request.status;
        const rtext = request.responseText;
        var had_error = false;
        var error_message = `status ${status}, response ${rtext}`;
        ldebug(`status: ${status}, response: ${rtext}`);

        if (status >= 200 && status < 400) { // success
            try {
                // TODO handle json parsing defensively here
                const resps = request.response;
                ldebug(`success: ${resps}`);
                const response = JSON.parse(resps);
                const vis = rawToVisits(response);
                cb(vis);
            } catch (err) {
                had_error = true;
                error_message = error_message.concat(String(err));
                console.error(err);
            }
        } else {
            had_error = true;
            if (status == 0) {
                error_message = error_message.concat(` ${endpoint} must be unavailable `);
            }
        }

        if (had_error) {
            lerror(`ERROR: ${error_message}`);
            showNotification(`ERROR: ${error_message}`);
            // TODO crap, doesn't really seem to respect urgency...
        }
    };
    request.onerror = () => {
        console.error(request);
    };

    request.setRequestHeader("Content-Type", "application/json;charset=UTF-8");
    request.send(data);
}

function getBackendVisits(u: Url, opts: Options, cb: (Visits) => void) {
    return queryBackendCommon({url: u}, opts, 'visits', cb);
}


// TODO FIXME include browser too..
export async function searchVisits(u: Url): Promise<Visits> {
    const opts = await get_options_async();
    return new Promise((cb) => queryBackendCommon({url: u}, opts, 'search', cb));
}

export async function searchAround(timestamp: number): Promise<Visits> {
    const opts = await get_options_async();
    return new Promise((cb) => queryBackendCommon({
        timestamp: timestamp,
    }, opts, 'search_around', cb));
}

function getDelayMs(/*url*/) {
    return 10 * 60 * 1000; // TODO do something smarter... for some domains we want it to be without delay
}

const LOCAL_TAG = 'local';


async function getChromeVisits(url: Url): Promise<Visits> {
    // $FlowFixMe
    const results = await new Promise((cb) => chrome.history.getVisits({url: url}, cb));

    // without delay you will always be seeing it as visited
    // but could be a good idea to make it configurable; e.g. sometimes we do want to know immediately. so could do domain-based delay or something like that?
    const delay = getDelayMs();
    const current = new Date();

    // ok, visitTime returns epoch which gives the correct time combined with new Date

    const times: Array<Date> = results.map(r => new Date(r['visitTime'])).filter(dt => current - dt > delay);
    // TODO FIXME not sure if need to normalise..
    const visits = times.map(t => new Visit(url, url, t, [LOCAL_TAG]));
    return new Visits(visits);
}

type Reason = string;

function normalisedHostname(url: Url): string {
    const _hostname = new URL(url).hostname;
    const hostname = normaliseHostname(_hostname);
    return hostname;
}

async function isBlacklisted(url: Url): Promise<?Reason> {
    // TODO perhaps use binary search?
    const hostname = normalisedHostname(url);
    const opts = await get_options_async();
    // for now assumes it's exact domain match domain level
    if (opts.blacklist.includes(hostname)) {
        return "User-defined blacklist";
    }
    const domains_url = chrome.runtime.getURL('shallalist/finance/banking/domains');
    const resp = await fetch(domains_url);
    const domains = (await resp.text()).split('\n');
    if (domains.includes(hostname)) {
        return "'Banking' blacklist";
    }
    return null;
}

type Result = Visits | Blacklisted;

export async function getVisits(url: Url): Promise<Result> {
    const bl = await isBlacklisted(url);
    if (bl != null) {
        return new Blacklisted(url, bl);
    }
    // NOTE sort of a problem with chrome visits that they don't respect normalisation.. not sure if there is much to do with it
    const chromeVisits = await getChromeVisits(url);
    const opts = await get_options_async();
    const backendVisits = await new Promise(cb => getBackendVisits(url, opts, cb));
    const allVisits = backendVisits.visits.concat(chromeVisits.visits);
    return new Visits(allVisits);
}

type IconStyle = {
    icon: string,
    title: string,
    text: ?string,
};


// TODO this can be tested?
function getIconStyle(visits: Result): IconStyle {
    if (visits instanceof Blacklisted) {
        return {icon: 'images/ic_blacklisted_48.png', title: `Blacklisted: ${visits.reason}`, text: null};
    }

    const vcount = visits.visits.length;
    if (vcount === 0) {
        return {icon: 'images/ic_not_visited_48.png', title: 'Not visited', text: null};
    }
    const contexts = visits.contexts();
    const ccount = contexts.length;
    if (ccount > 0) {
        return {icon: 'images/ic_visited_48.png'    , title: `${vcount} visits, ${ccount} contexts`, text: ccount.toString()};
    }
    // TODO a bit ugly, but ok for now.. maybe cut off by time?
    const boring = visits.visits.every(v => v.tags.length == 1 && v.tags[0] == LOCAL_TAG);
    if (boring) {
        // TODO not sure if worth distinguishing..
        return {icon: "images/ic_boring_48.png"     , title: `${vcount} visits (local only)`, text: null};
    } else {
        return {icon: "images/ic_blue_48.png"       , title: `${vcount} visits`, text: null};
    }
}

function chromeTabsQueryAsync(opts): Promise<Array<chrome$Tab>> {
    return new Promise((cb) => chrome.tabs.query(opts, cb));
}

async function updateState () {
    const tabs = await chromeTabsQueryAsync({'active': true});
    // TODO why am I getting multiple results???
    const atab = tabs[0];
    const url = unwrap(atab.url);
    const tabId = unwrap(atab.id);

    if (ignored(url)) {
        log("ignoring %s", url);
        return;
    }

    const visits = await getVisits(url);
    let {icon, title, text} = getIconStyle(visits);
    for (const action of ACTIONS) {
        // $FlowFixMe
        action.setIcon({
            path: icon,
            tabId: tabId,
        });
        // $FlowFixMe
        action.setTitle({
            title: title,
            tabId: tabId,
        });
        if (text != null) {
            // $FlowFixMe
            action.setBadgeText({
                text: text,
            });
        }
    }
    // TODO if it's part of actions only?
    chrome.pageAction.show(tabId);

    if (visits instanceof Visits) {
            // TODO maybe store last time we showed it so it's not that annoying... although I definitely need js popup notification.
            const locs = visits.contexts().map(l => l == null ? null : l.title);
            if (locs.length !== 0) {
                showTabNotification(tabId, `${locs.length} contexts!\n${locs.join('\n')}`);
            }

            chrome.tabs.executeScript(tabId, {
                file: 'sidebar.js',
            }, () => {
                chrome.tabs.executeScript(tabId, {
                    code: `bindSidebarData(${JSON.stringify(visits)})`
                });
            });
    }
}

// TODO check for blacklist here as well
// TODO FIXME ugh. this can be tested on some static page... I guess?
function showDots(tabId, options: Options) {
    chrome.tabs.executeScript(tabId, {
        code: `
     const aaa = document.getElementsByTagName("a");
     const domain = document.domain;

     const urls = new Set([]);
     for (var i = 0; i< aaa.length; i++) {
         urls.add(aaa[i].getAttribute('href'));
     }
     urls.delete("#");
     urls.delete(null);
     const aurls = new Set([]);
     for (let u of urls) {
         if (u.startsWith('javascript')) {
             continue
         } else if (u.startsWith('/')) {
             aurls.add(domain + u);
         } else {
             aurls.add(u);
         }
     }
     // TODO move more stuff to background??
     Array.from(aurls)
 `
    }, results => {
        if (results == null) {
            throw "shouldn't happen";
        }
        // TODO FIXME filter these by blacklist as well?
        const res = results[0];
        if (res == null) {
            console.error("Weird, res is null. Not doing anything");
            return;
        }
        // TODO check if zero? not sure if necessary...
        // TODO maybe, I need a per-site extension?

        reqwest({
            url: `${options.host}/visited`
            , method: 'post'
            , contentType: 'application/json'
            , headers: {
                'Authorization': "Basic " + btoa(options.token),
            }
            , data: JSON.stringify({
                "urls": res,
            })
            , success: resp => {
                // TODO ok, we received exactly same elements as in res. now what??
                // TODO cache results internally? At least for visited. ugh.
                // TODO make it custom option?
                const vis = {};
                for (var i = 0; i < res.length; i++) {
                    vis[res[i]] = resp[i];
                }
                // TODO make a map from it..
                chrome.tabs.insertCSS(tabId, {
                    code: `
.wereyouhere-visited:after {
  content: "⚫";
  color: #FF4500;
  vertical-align: super;
  font-size: smaller;

  user-select: none;

  position:absolute;
  z-index:100;
}
`
                });
                chrome.tabs.executeScript(tabId, {
                    code: `
const vis = ${JSON.stringify(vis)}; // madness!
for (var i = 0; i < aaa.length; i++) {
    var a_tag = aaa[i];
    var url = a_tag.getAttribute('href');
    if (url == null) {
        continue;
    }
    if (url.startsWith('/')) {
        url = domain + url;
    }
    if (vis[url] == true) {
        // console.log("adding class to ", a_tag);
        a_tag.classList.add('wereyouhere-visited');
    }
}
`
                });
            }
            , error: err => {
                console.error(err);
                showNotification(err.responseText);
            }
        });

    });
}

// ok, looks like this one was excessive..
// chrome.tabs.onActivated.addListener(updateState);

function ignored(url: string): boolean {
    // not sure why about:blank is loading like 5 times.. but this seems to fix it
    if (url.match('chrome://') != null || url.match('chrome-devtools://') != null || url == 'about:blank') {
        return true;
    }
    if (url === 'https://www.google.com/_/chrome/newtab?ie=UTF-8') { // ugh, not sure how to dix that properly
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

        showDots(detail.tabId, opts);
        // updateState();
    });
});
*/

// chrome.tabs.onReplaced.addListener(updateState);

chrome.tabs.onCreated.addListener((tab) => {
    ldebug("onCreated %s", tab);
});


// $FlowFixMe
chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
    delete tab.favIconUrl; // too spammy in logs
    ldebug("onUpdated %s %s", tab, info);

    const url = tab.url;
    if (url == null) {
        ldebug('onUpdated: ignoring as URL is not set');
        return;
    }

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

    if (info['status'] === 'complete') {
        linfo('requesting! %s', url);
        await updateState();
    }
});


async function getActiveTab(): Promise<?chrome$Tab> {
    const tabs = await chromeTabsQueryAsync({'active': true});
    const tab = tabs[0];
    const url = unwrap(tab.url);
    // TODO ugh duplication
    if (ignored(url)) {
        log("ignoring %s", url); // TODO not sure when it should be handled...
        return null;
    }
    return tab;
}

async function showActiveTabNotification(text: string, color: string): Promise<void> {
    const atab = await getActiveTab();
    if (atab != null) { // TODO FIXME
        showTabNotification(unwrap(atab.id), text, color);
    }
}

// $FlowFixMe
chrome.runtime.onMessage.addListener(async (msg) => {
    if (msg.method == Methods.GET_SIDEBAR_VISITS) {
        const atab = await getActiveTab();
        if (atab != null) { // means it's ignored
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
    } else if (msg.method == Methods.SEARCH_VISITS_AROUND) {
        const timestamp = msg.timestamp; // TODO FIXME epoch?? 
        const params = new URLSearchParams();
        // TODO str??
        params.append('timestamp', timestamp.toString());
        const search_url = chrome.extension.getURL('search.html') + '?' + params.toString();
        chrome.tabs.create({'url': search_url});
    }
    return false;
});

for (const action of ACTIONS) {
    // $FlowFixMe
    action.onClicked.addListener(async tab => {
        const url = unwrap(tab.url);
        const tid = unwrap(tab.id);
        if (ignored(url)) {
            showNotification(`${url} can't be handled`);
            return;
        }
        const bl = await isBlacklisted(url);
        if (bl != null) {
            showBlackListedNotification(tid, new Blacklisted(url, bl));
            // TODO show popup; suggest to whitelist?
        } else {
            chrome.tabs.executeScript(tid, {file: 'sidebar.js'}, () => {
                chrome.tabs.executeScript(tid, {code: 'toggleSidebar();'});
            });
        }
    });
}

// $FlowFixMe // err, complains at Promise but nevertheless works
chrome.commands.onCommand.addListener(async cmd => {
    if (cmd === 'show_dots') {
        // TODO actually use show dots setting?
        const opts = await get_options_async();
        const atab = await getActiveTab();
        if (atab == null) {
            // means it's ignored
            // TODO ugh, would be useful to have tab id here
            showIgnoredNotification(0, 'TODO URL');
        } else {
            const url = unwrap(atab.url);
            const tid = unwrap(atab.id);
            const bl = await isBlacklisted(url);
            if (bl != null) {
                showBlackListedNotification(tid, new Blacklisted(url, bl));
            } else {
                showDots(tid, opts);
            }
        }
    } else if (cmd == 'search') {
        // TODO FIXME get current tab url and pass as get parameter?
        chrome.tabs.create({ url: "search.html" });
    }
});


async function blackListDomain(e): Promise<void> {
    const url = unwrap(e.pageUrl);
    const hostname = normalisedHostname(url);

    const opts = await get_options_async();
    opts.blacklist.push(hostname);

    const ll = opts.blacklist.length;
    await showActiveTabNotification(`Added ${hostname} to blacklist (${ll} items now)`, 'blue');
    await setOptions(opts);
}

chrome.contextMenus.create({
    "title"   : "Blacklist domain",
    // $FlowFixMe
    "onclick" : blackListDomain,
});

// TODO make sure it's consistent with rest of blacklisting and precedence clearly stated
// chrome.contextMenus.create({
//     "title"   : "Blacklist page",
//     // $FlowFixMe
//     "onclick" : blackListPage,
// });

// chrome.contextMenus.create({
//     "title"   : "Whitelist page",
//     "onclick" : clickHandler,
// });
