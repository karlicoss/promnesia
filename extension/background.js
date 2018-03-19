// measure slowdown? Although it's async, so it's fine probably
var all_urls;

function wasVisited(url) {
    // TODO will be more elaborate, e.g. query local history
    return all_urls.has(url);
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
                title: "Was visited! TODO add date",
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

chrome.runtime.onInstalled.addListener(function() {
    chrome.storage.local.get(['history_json'], function(result) {
        var histfile = result.history_json;
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            // ugh, ideally should check that status is 200 etc, but that doesn't seem to work =/
            // TODO maybe swallowing exceptions here is a good idea?
            // could be paranoid and ignore if all_urls is already set?
            var list = JSON.parse(xhr.responseText);
            if (list.length > 0) {
                console.log("Loaded ", list.length, " urls");
                all_urls = new Set(list);
            }
        };
        xhr.open("GET", 'file:///' + histfile, true);
        xhr.send();
        // ugh, fetch api doesn't work with local uris
    });
});
