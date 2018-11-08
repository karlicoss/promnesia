export function setUrlsFile(path, cb) {
    chrome.storage.local.set({'urls_json_file': path}, cb);
}

export function getUrlsFile(cb) {
    chrome.storage.local.get({'urls_json_file': null}, res => cb(res.urls_json_file));
}
