// measure slowdown? Although it's async, so it's fine probably
var all_urls;

function getVisits(url) {
    return all_urls[url];
}

function wasVisited(url) {
    // TODO will be more elaborate, e.g. query local history
    return typeof getVisits(url) != "undefined";
}


chrome.tabs.onUpdated.addListener(function(tabId, changeInfo, tab) {
    // TODO ugh no simpler way??
    chrome.tabs.query({'active': true}, function (tabs) {
        // TODO why am I getting multiple results???
        var url = tabs[0].url;
        if (wasVisited(url)) {
            chrome.browserAction.setIcon({
                path: "eye-64-green.png",
                tabId: tab.id
            });
            chrome.browserAction.setTitle({
                title: "Was visited! " + String(getVisits(url)),
                tabId: tab.id
            });
        } else {
            chrome.browserAction.setIcon({
                path: "eye-64-red.png",
                tabId: tab.id
            });
            chrome.browserAction.setTitle({
                title: "Was not visited",
                tabId: tab.id
            });
        }
    });
});

function refreshMap () {
    chrome.storage.local.get(['history_json'], function(result) {
        var histfile = result.history_json;
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            // ugh, ideally should check that status is 200 etc, but that doesn't seem to work =/
            // TODO maybe swallowing exceptions here is a good idea?
            // could be paranoid and ignore if all_urls is already set?
            var map = JSON.parse(xhr.responseText);
            console.log(map);
            var len = Object.keys(map).length;
            if (len > 0) {
                console.log("Loaded ", len, " urls");
                all_urls = map;
                // TODO remove listener?
            }
        };
        xhr.open("GET", 'file:///' + histfile, true);
        xhr.send();
        // ugh, fetch api doesn't work with local uris
    });
}

chrome.runtime.onInstalled.addListener(refreshMap);

chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    if (request.method == 'getVisits') {
        chrome.tabs.query({'active': true}, function (tabs) {
            var url = tabs[0].url;
            sendResponse(getVisits(url));
        });
        return true; // this is important!! otherwise message will not be sent?
    } else if (request.method == 'refreshMap') {
        refreshMap();
        return true;
    }
});
