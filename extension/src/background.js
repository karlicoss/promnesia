/* @flow */

import {Visits, unwrap} from './common';
import {normalise_url} from './normalise';
import {getUrlsFile} from './options';

// measure slowdown? Although it's async, so it's fine probably
var all_urls = null;

type Url = string;
type VisitsMap = {[Url]: Visits};
// type VisitsMap = {}

function rawMapToVisits(map): ?VisitsMap {
    const len = Object.keys(map).length;
    if (len == 0) {
        return null; // TODO not sure if that's really necessary
    }
    var result = {};
    Object.keys(map).map(function (url /*index*/) {
        const vis = map[url];
        result[url] = new Visits(vis[0], vis[1]);
    });
    return result;
}

function refreshMap (cb: ?(VisitsMap) => void) {
    console.log("Urls map refresh requested!");
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

function getMap(cb: (VisitsMap) => void) {
    // not sure why is this even necessary... just as extensions is running, all_urls is getting set to null occasionally
    if (all_urls !== null) {
        cb(all_urls);
    } else {
        refreshMap(cb);
        // TODO if still null, return dummy visits with 'not set' message?
    }
}


chrome.runtime.onInstalled.addListener(function () {refreshMap(null); });

function getDelay(/*url*/) {
    return 24 * 60 * 60 * 1000; // TODO do something smarter... for some domains we want it to be without delay
}

function getChromeVisits(url, cb /* Visits -> Void */) {
    // $FlowFixMe
    chrome.history.getVisits(
        {url: url},
        function (results) {
            var delay = getDelay(url);
            var current = new Date();
            var times = results.map(r => new Date(r['visitTime'])).filter(dt => current - dt > delay);
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
                return format_date(g[0]) + " " + format_time(g[0]) + "--" + format_time(g[g.length - 1]) + '  (chr)';
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
    getMap(map => {
        var nurl = normalise_url(url);
        console.log("Original: %s", url);
        console.log("Normalised: %s", nurl);
        var v = map[nurl];
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

function updateState () {
    // TODO ugh no simpler way??
    chrome.tabs.query({'active': true}, function (tabs) {
        // TODO why am I getting multiple results???
        let atab = tabs[0];
        let url = unwrap(atab.url);
        // $FlowFixMe
        let tabId = atab.tabId;
        getVisits(url, function (visits) {
            if (visits.visits.length > 0) { // TODO check if visits are trivial?
                chrome.browserAction.setIcon({
                    path: "images/ic_visited_48.png",
                    tabId: tabId
                });
                chrome.browserAction.setTitle({
                    title: "Was visited! " + String(visits),
                    tabId: tabId
                });
            } else {
                chrome.browserAction.setIcon({
                    path: "images/ic_not_visited_48.png",
                    tabId: tabId
                });
                chrome.browserAction.setTitle({
                    title: "Was not visited",
                    tabId: tabId
                });
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
        refreshMap();
        return true;
    }
    return false;
});

// TODO what about default listener??
chrome.browserAction.onClicked.addListener(tab => {
    chrome.tabs.executeScript(tab.id, {file: 'sidebar.js'});
});
