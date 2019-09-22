/* @flow */

// $FlowFixMe
export function awrap(fn, ...args: Array<any>): Promise<any> {
    return new Promise((resolve, reject) => {
        const cbb = (...xxx) => {
            const err = chrome.runtime.lastError;
            if (err) {
                reject(err);
            }
            resolve(...xxx);
        };
        // ugh. can't pass proper typed args down to chrome interfaces?
        // $FlowFixMe
        fn(...args, cbb);
    });
}

export function chromeTabsExecuteScriptAsync(tabId: number, opts: any) {
    return awrap(chrome.tabs.executeScript, tabId, opts);
}

export function chromeTabsInsertCSS(tabId: number, opts: any) {
    return awrap(chrome.tabs.insertCSS, tabId, opts);
}

export function chromeTabsQueryAsync(opts: any): Promise<Array<chrome$Tab>> {
    return awrap(chrome.tabs.query, opts);
}

export function chromeRuntimeGetPlatformInfo(): Promise<chrome$PlatformInfo> {
    return awrap(chrome.runtime.getPlatformInfo);
}

export function chromeRuntimeSendMessage(msg: any) {
    return awrap(chrome.runtime.sendMessage, msg);
}

export function chromeTabsGet(tabId: number) {
    return awrap(chrome.tabs.get, tabId);
}
