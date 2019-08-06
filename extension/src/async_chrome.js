/* @flow */

// $FlowFixMe
export function chromeTabsExecuteScriptAsync(...args) {
    // $FlowFixMe
    return new Promise(cb => chrome.tabs.executeScript(...args, cb));
}

// $FlowFixMe
export function chromeTabsInsertCSS(...args) {
    // $FlowFixMe
    return new Promise(cb => chrome.tabs.insertCSS(...args, cb));
}

export function chromeTabsQueryAsync(opts: any): Promise<Array<chrome$Tab>> {
    return new Promise(cb => chrome.tabs.query(opts, cb));
}


