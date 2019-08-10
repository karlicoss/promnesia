/* @flow */

// $FlowFixMe
export function chromeTabsExecuteScriptAsync(...args) {
    // $FlowFixMe
    return new Promise(cb => {
        chrome.tabs.executeScript(...args, cb);
        const err = chrome.runtime.lastError;
        if (err) {
            throw err;
        }
    });
}

// $FlowFixMe
export function chromeTabsInsertCSS(...args) {
    // $FlowFixMe
    return new Promise(cb => chrome.tabs.insertCSS(...args, cb));
}

export function chromeTabsQueryAsync(opts: any): Promise<Array<chrome$Tab>> {
    return new Promise(cb => chrome.tabs.query(opts, cb));
}


export function chromeRuntimeGetPlatformInfo(): Promise<chrome$PlatformInfo> {
    return new Promise(cb => chrome.runtime.getPlatformInfo(cb));
}

