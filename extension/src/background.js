/* @flow */

import type {Locator, Tag, Url, Second} from './common';
import {Visit, Visits, unwrap} from './common';
import {normalise_url} from './normalise';
import type {Options} from './options';
import {get_options, get_options_async} from './options';
// $FlowFixMe
import reqwest from 'reqwest';

const ACTIONS = [chrome.browserAction, chrome.pageAction]; // TODO dispatch depending on android/desktop?

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

export function showTabNotification(tabId: number, text: string) {
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
  backgroundColor: "green",
}).showToast();
    `    });
      });
    });
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
        const vctx: ?string = v['context'];
        const vloc: ?Locator = v['locator']
        const vdur: ?Second = v['duration'];
        return new Visit(dt, vtags, vctx, vloc, vdur);
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

function getBackendVisits(u: Url, opts: Options, cb: (Visits) => void) {
    const data = JSON.stringify({
        'url': u,
    });

    const request = new XMLHttpRequest();

    const endpoint = `${opts.host}/visits`;
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
        log(`status: ${status}, response: ${rtext}`);

        if (status >= 200 && status < 400) { // success
            try {
                // TODO handle json parsing defensively here
                const response = JSON.parse(request.response);
                log(`success: ${response}`);
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
            console.error(`[background] ERROR: ${error_message}`);
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


function getDelayMs(/*url*/) {
    return 10 * 60 * 1000; // TODO do something smarter... for some domains we want it to be without delay
}

const LOCAL_TAG = 'local';

function getChromeVisits(url: Url, cb: (Visits) => void) {
    // $FlowFixMe
    chrome.history.getVisits(
        {url: url},
        function (results) {
            // without delay you will always be seeing it as visited
            // but could be a good idea to make it configurable; e.g. sometimes we do want to know immediately. so could do domain-based delay or something like that?
            const delay = getDelayMs();
            const current = new Date();

            // ok, visitTime returns epoch which gives the correct time combined with new Date

            const times: Array<Date> = results.map(r => new Date(r['visitTime'])).filter(dt => current - dt > delay);
            const visits = times.map(t => new Visit(t, [LOCAL_TAG]));
            cb(new Visits(visits));
        }
    );
}

function getVisits(url: Url, cb: (Visits) => void) {
    var nurl = normalise_url(url);
    // TODO allow blacklisting on level of base url, that should be enough.. don't need full scale normalisation for that 
    log("original: %s -> normalised %s", url, nurl);

    get_options(opts => {
        // NOTE sort of a problem with chrome visits that they don't respect normalisation.. not sure if there is much to do with it
        getChromeVisits(url, chr_visits => {
            // TODO hmm. it's confusing since blacklisting only results in not querying on server, so not sure if only local visits are of any use?
            if (opts.blacklist.includes(nurl)) {
                log('%s is blacklisted! ignoring it', nurl);
                cb(chr_visits);
            } else {
                getBackendVisits(url, opts, backend_visits => {
                    const all_visits = backend_visits.visits.concat(chr_visits.visits);
                    cb(new Visits(all_visits));
                });
            }
        });
    });
}

function getIconAndTitle (visits: Visits) {
    if (visits.visits.length === 0) {
        return ['images/ic_not_visited_48.png', 'Was not visited'];
    }
    const contexts = visits.contexts();
    if (contexts.length > 0) {
        return ['images/ic_visited_48.png'    , 'Was visited (has contexts)'];
    }
    // TODO a bit ugly, but ok for now.. maybe cut off by time?
    const boring = visits.visits.every(v => v.tags.length == 1 && v.tags[0] == LOCAL_TAG);
    if (boring) {
        return ["images/ic_boring_48.png"     , "Was visited (boring)"];
    } else {
        return ["images/ic_blue_48.png"       , "Was visited"];
    }
}

function updateState () {
    // TODO ugh no simpler way??
    chrome.tabs.query({'active': true}, function (tabs) {
        // TODO why am I getting multiple results???
        let atab = tabs[0];
        let url = unwrap(atab.url);
        let tabId = unwrap(atab.id);

        if (ignored(url)) {
            log("ignoring %s", url);
            return;
        }

        getVisits(url, visits => {
            let res = getIconAndTitle(visits);
            let icon = res[0];
            let title = res[1];
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
            }
            // TODO if it's part of actions only?
            chrome.pageAction.show(tabId);

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
        });
    });
}

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
    ldebug("!!!!!! CREATED %s", tab);
});

chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
    ldebug("!!!!!! UPDATED %s %s", tab, info);

    const url = tab.url;
    if (url == null) {
        ldebug('URL is not set; ignoring');
        return;
    }

    if (ignored(url)) {
        linfo("ignoring %s", url);
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
        updateState();
    }
});

type Tab = any;

function getActiveTab(cb: (Tab) => void) {
    chrome.tabs.query({'active': true}, tabs => {
        const tab = tabs[0];
        const url = unwrap(tab.url);
        // TODO ugh duplication
        if (ignored(url)) {
            log("ignoring %s", url);
            return;
        }
        cb(tab);
    });
}

function getActiveTabAsync(): Promise<Tab> {
    // TODO FIXME reject
    return new Promise((cb) => getActiveTab(cb));
}

// $FlowFixMe
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.method == 'getActiveTabVisits') {
        getActiveTab(tab => {
            getVisits(tab.url, visits => {
                sendResponse(visits);
            });
        });
        return true; // this is important!! otherwise message will not be sent?
    }
    return false;
});

for (const action of ACTIONS) {
    action.onClicked.addListener(tab => {
        const url = unwrap(tab.url);
        if (ignored(url)) {
            showNotification(`${url} can't be handled`);
            return;
        }
        chrome.tabs.executeScript(tab.id, {file: 'sidebar.js'}, () => {
            chrome.tabs.executeScript(tab.id, {code: 'toggleSidebar();'});
        });
    });
}

// $FlowFixMe // err, complains at Promise but nevertheless works
chrome.commands.onCommand.addListener(async cmd => {
    if (cmd === 'show_dots') {
        // TODO actually use show dots setting?
        const opts = await get_options_async();
        const atab = await getActiveTabAsync();
        showDots(atab.tabId, opts);
    }
});
