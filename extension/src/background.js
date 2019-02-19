/* @flow */

import type {Url, VisitsMap} from './common';
import {Visit, Visits, unwrap} from './common';
import {normalise_url} from './normalise';
import type {Options} from './options';
import {get_options} from './options';
// $FlowFixMe
import reqwest from 'reqwest';

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
    // TODO not sure, maybe we want to distinguish..
    if (vis == null) {
        return new Visits([], []);
    }

    const visits = vis[0];
    const contexts: Array<string> = vis[1];
    return new Visits(visits.map(v => {
        const vtime: string = v[0];
        const vtags: Array<string> = v[1];
        return new Visit(vtime, vtags);
    }), contexts);
}

// $FlowFixMe
function log() {
    const args = [];
    for (var i = 1; i < arguments.length; i++) {
        args.push(arguments[i]);
    }
    console.log('[background] ' + arguments[0], ...args);
}


// TODO definitely need to use something very lightweight for json requests..

// TODO better name?
function getJsonVisits(u: Url, opts: Options, cb: (Visits) => void) {
    // TODO ok, here we want to do an async request

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

function getChromeVisits(url: Url, cb: (Visits) => void) {
    // $FlowFixMe
    chrome.history.getVisits(
        {url: url},
        function (results) {
            const delay = getDelayMs();
            const current = new Date();
            const times: Array<Date> = results.map(r => new Date(r['visitTime'])).filter(dt => current - dt > delay);
            var groups = [];
            var group = [];

            function dump_group () {
                if (group.length > 0) {
                    groups.push(group);
                    group = [];
                }
            }

            function split_date_time (dt) {
                var d = new Date(dt.getTime() - dt.getTimezoneOffset() * 60000);
                var spl = d.toISOString().split('Z')[0].split('T');
                return [spl[0], spl[1].substring(0, 5)];
            }

            function format_time (dt) {
                return split_date_time(dt)[1];
            }

            // UGH there are no decent custom time format functions in JS..
            function format_date (dt) {
                var options = {
                    day  : 'numeric',
                    month: 'short',
                    year : 'numeric',
                };
                return dt.toLocaleDateString("en-GB", options);
            }

            function format_group (g) {
                const dts = format_date(g[0]) + " " + format_time(g[0]) + "--" + format_time(g[g.length - 1]);
                const tags = ["chr"];
                return new Visit(dts, tags);
            }

            var delta = 20 * 60 * 1000; // make sure it matches with python
            for (const t of times) {
                const last = group.length == 0 ? t : group[group.length - 1];
                if (t - last > delta) {
                    dump_group();
                }
                group.push(t);
            }
            dump_group();


            var visits = groups.map(format_group);
            visits.reverse();
            // TODO might be a good idea to have some delay for showing up items in extended history, otherwise you will always be seeing it as visited
            // also could be a good idea to make it configurable; e.g. sometimes we do want to know immediately. so could do domain-based delay or something like that?
            cb(new Visits(visits, []));
        }
    );
}

function getMapVisits(url: Url, cb: (Visits) => void) {
    var nurl = normalise_url(url);
    log("original: %s -> normalised %s", url, nurl);
    get_options(opts => {
        if (opts.blacklist.includes(nurl)) {
            log('%s is blacklisted! ignoring it', nurl);
            return;
        }
        getJsonVisits(nurl, opts, v => {
            if (v) {
                cb(v);
            } else {
                cb(new Visits([], []));
            }
        });
    });
}

function getVisits(url: Url, cb: (Visits) => void) {
    getChromeVisits(url, function (chr_visits) {
        getMapVisits(url, function (map_visits) {
            cb(new Visits(
                map_visits.visits.concat(chr_visits.visits),
                map_visits.contexts.concat(chr_visits.contexts)
                // TODO actually, we should sort somehow... but with dates as strings gonna be tedious...
                // maybe, get range of timestamps from python and convert in JS? If we're doing that anyway...
                // also need to share domain filters with js...
                // for now just prefer map visits to chrome visits
            ));
        });
    });
}

function getIconAndTitle (visits: Visits) {
    if (visits.visits.length === 0) {
        return ["images/ic_not_visited_48.png", "Was not visited"];
    }
    // TODO a bit ugly, but ok for now.. maybe cut off by time?
    const boring = visits.visits.every(v => v.tags.length == 1 && v.tags[0] == "chr");
    if (boring) {
        return ["images/ic_boring_48.png"     , "Was visited (boring)"];
    } else {
        return ["images/ic_visited_48.png"    , "Was visited!"];
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

        getVisits(url,  function (visits) {
            let res = getIconAndTitle(visits);
            let icon = res[0];
            let title = res[1];
            chrome.browserAction.setIcon({
                path: icon,
                tabId: tabId,
            });
            chrome.browserAction.setTitle({
                title: title,
                tabId: tabId,
            });

            // TODO maybe store last time we showed it so it's not that annoying... although I definitely need js popup notification.
            if (visits.contexts.length > 0) {
                // TODO add context sources to notification message...
                // TODO need settings...
                showTabNotification(tabId, `${visits.contexts.length} contexts!`);
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

// TODO ehh... not even sure that this is correct thing to do...
// $FlowFixMe
chrome.webNavigation.onDOMContentLoaded.addListener(detail => {
    const url = unwrap(detail.url);
    if (detail.frameId != 0) {
        log('ignoring child iframe for %s', url);
        return;
    }

    if (ignored(url)) {
        log("ignoring %s", url);
        return;
    }
    // https://kk.org/thetechnium/
    log(`finished loading DOM ${JSON.stringify(detail)}`);
    get_options(opts => {
        if (opts.dots) {
            showDots(detail.tabId, opts);
        }
        // updateState();
    });
});
// chrome.tabs.onReplaced.addListener(updateState);


chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
    const url = unwrap(tab.url);

    if (ignored(url)) {
        log("ignoring %s", url);
        return;
    }
    // right, tab updated triggered quite a lot, e.g. when the title is blinking
    // log(`TAB UPDATED ${url} ${info}`);
    // console.log(info);
    // ok, so far there are basically two cases
    // 1. you open new tab. in that case 'url' won't be passed but onDomContentLoaded will be triggered
    // 2. you navigate within the same tab, e.g. on youtube. then url will be passed, but onDomContentLoaded doesn't trigger. TODO not sure if it's always the case. maybe it's only YT
    // TODO shit, so we might need to hide previous dots? ugh...

    // page refresh: loading -> complete (no url at any point)
    // clicking on link: loading (url) -> complete
    // opening new link: loading -> loading (url) -> complete
    // ugh. looks like 'complete' is the most realiable???
    // but, I checked with 'complete' and sometimes it would reload many things with loading -> complete..... shit.

    // also if you, say, go to web.telegram.org it's gonna show multiple notifications due to redirect... but perhaps this can just be suppressed..

    log(JSON.stringify(info));
    if (info['status'] === 'loading' && info['url'] != null) {
        log(`requesting! ${url}`);
        updateState();
    }
});

// $FlowFixMe
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    if (request.method == 'getActiveTabVisits') {
        chrome.tabs.query({'active': true}, function (tabs) {
            var url = unwrap(tabs[0].url);
            // TODO ugh duplication
            if (ignored(url)) {
                log("ignoring %s", url);
                return;
            }

            getVisits(url, function (visits) {
                sendResponse(visits);
            });
        });
        return true; // this is important!! otherwise message will not be sent?
    }
    return false;
});

chrome.browserAction.onClicked.addListener(tab => {
    const url = unwrap(tab.url);
    if (ignored(url)) {
        showNotification(`${url} can't be handled`);
        return;
    }
    chrome.tabs.executeScript(tab.id, {file: 'sidebar.js'}, () => {
        chrome.tabs.executeScript(tab.id, {code: 'toggleSidebar();'});
    });
});
