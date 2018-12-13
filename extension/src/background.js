/* @flow */

import type {Url, VisitsMap} from './common';
import {Visit, Visits, unwrap} from './common';
import {normalise_url} from './normalise';
import {getUrlsFile} from './options';

// $FlowFixMe
import idb from 'idb';
// measure slowdown? Although it's async, so it's fine probably

// TODO ok, in case of issues just clear /home/karlicos/.config/google-chrome/Default/IndexedDB/chrome-extension_lilgepckbpdcefoofonbalbecljohhhj_0.indexeddb.leveldb
const UDB = 'urls-db';
const US = 'urls-store';

function getDb() {
    return idb.open(UDB, 1, udb => {
        console.log('Upgraded db');
        udb.createObjectStore(US);
    });
}


function putVisitsMap(mm: VisitsMap) {
    getDb().then(db => {
        const tx = db.transaction(US, 'readwrite');
        const os = tx.objectStore(US);
        const kk = Object.keys(mm);
        console.log('updating object store...');
        for (var i = 0; i < kk.length; i++) {
            if (i % 5000 == 0) {
                console.log(`handling visit ${i}/${kk.length}`);
            }
            const url = kk[i];
            const vis = mm[url];
            os.put(vis, url);
        }
        return os.complete;
    }).then(xx => console.log("finished updating the database"), err => console.log("ERROR! " + err));
    // TODO read from json iteratively so we don't have memory spike?? I gues we can't really...
}

function rawMapToVisits(map): ?VisitsMap {
    const len = Object.keys(map).length;
    if (len == 0) {
        return null; // TODO not sure if that's really necessary
    }
    var result = {};
    Object.keys(map).map(function (url /*index*/) {
        const vis = map[url];
        const visits = vis[0];
        var contexts: Array<string> = vis[1];
        // TODO tried that to save up db space, but that doesn't really help...
        // if (contexts.length == 0) {
        //     contexts = null;
        // }

        result[url] = new Visits(visits.map(v => {
            const vtime: string = v[0];
            const vtags: Array<string> = v[1];
            return new Visit(vtime, vtags);
        }), contexts);
    });
    return result;
}

function showNotification(text: string) {
    if (Notification.permission !== "granted") {
        Notification.requestPermission();
    } else {
        // TODO ugh. is there no way to show in-browser only notification??
        const notification = new Notification(
            'wereyouhere',
            // $FlowFixMe
            {body: text},
        );
    }
}

function refreshMap (cb: ?(VisitsMap) => void) {
    console.log("Urls map refresh requested!");
    showNotification("requested url map reloading");
    getUrlsFile(histfile => {
        if (histfile === null) {
            console.log("No urls file! Please set it in extension options!");
            return;
        }

        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            // ugh, ideally should check that status is 200 etc, but that doesn't seem to work =/
            // TODO maybe swallowing exceptions here is a good idea?
            // could be paranoid and ignore if all_urls is already set?
            if (xhr.readyState != xhr.DONE) {
                return;
            }
            const map = JSON.parse(xhr.responseText);
            const len = Object.keys(map).length;
            console.log("Loaded map of length ", len);
            const visits = rawMapToVisits(map);
            if (visits) {
                putVisitsMap(visits);
                if (cb) {
                    cb(visits);
                }
            }
            // TODO warn otherwise?
            // TODO remove listener?
        };
        xhr.open("GET", 'file:///' + histfile, true);
        xhr.send();
        // ugh, fetch api doesn't work with local uris
    });
}

function getJsonVisits(u: Url, cb: (Visits) => void) {
    getDb().then(db => {
        db.transaction(US).objectStore(US).get(u).then(cb); // TODO error??
    });
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
    console.log("Original: %s", url);
    console.log("Normalised: %s", nurl);
    getJsonVisits(nurl, v => {
        if (v) {
            cb(v);
        } else {
            cb(new Visits([], []));
        }
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
        // $FlowFixMe
        let tabId = atab.tabId;
        getVisits(url, function (visits) {
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
                showNotification('contexts are available for this link!');
            }
        });
    });
}

// erm.. all these things are pretty confusing, but that seems to work... just onUpdated didnt
chrome.tabs.onActivated.addListener(updateState);
chrome.tabs.onUpdated.addListener(updateState);
// chrome.tabs.onReplaced.addListener(updateState);

// $FlowFixMe
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    if (request.method == 'getVisits') {
        chrome.tabs.query({'active': true}, function (tabs) {
            var url = unwrap(tabs[0].url);
            getVisits(url, function (visits) {
                sendResponse(visits);
            });
        });
        return true; // this is important!! otherwise message will not be sent?
    } else if (request.method == 'refreshMap') {
        console.log('refreshing map (requested by message listener)');
        refreshMap();
        return true;
    }
    return false;
});

// TODO what about default listener??
chrome.browserAction.onClicked.addListener(tab => {
    chrome.tabs.executeScript(tab.id, {file: 'sidebar.js'});
});


const refreshMapAlarm = 'refreshUrlMap';
const delayMinutes = 20; // TODO ??

function setupAlarm() {
    console.log('refreshing map (initial)');
    refreshMap(null);
    chrome.alarms.get(refreshMapAlarm, function(alarm) {
        if (!alarm) {
            chrome.alarms.create(refreshMapAlarm, {
                delayInMinutes: delayMinutes,
                periodInMinutes: delayMinutes,
            });
        }
    });
}


chrome.runtime.onInstalled.addListener(setupAlarm);
chrome.runtime.onStartup.addListener(setupAlarm);

function onAlarm(alarm) {
    switch (alarm.name) {
    case refreshMapAlarm:
        console.log('refreshing map (alarm)');
        refreshMap(null);
        break;
    default:
        break;
    }
}
chrome.alarms.onAlarm.addListener(onAlarm);
