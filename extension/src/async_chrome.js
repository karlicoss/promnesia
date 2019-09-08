/* @flow */

function wrap(fn, ...args: Array<any>): Promise<any> {
    return new Promise((resolve, reject) => {
        const cbb = (...xxx) => {
            const err = chrome.runtime.lastError;
            if (err) {
                reject(err);
            }
            resolve(...xxx);
        };
        fn(...args, cbb);
    });
}

export function chromeTabsExecuteScriptAsync(tabId: number, opts: any) {
    return wrap(chrome.tabs.executeScript, tabId, opts);
}

export function chromeTabsInsertCSS(tabId: number, opts: any) {
    return wrap(chrome.tabs.insertCSS, tabId, opts);
}

export function chromeTabsQueryAsync(opts: any): Promise<Array<chrome$Tab>> {
    return wrap(chrome.tabs.query, opts);
}


export function chromeRuntimeGetPlatformInfo(): Promise<chrome$PlatformInfo> {
    return wrap(chrome.runtime.getPlatformInfo);
}

export function chromeRuntimeSendMessage(msg: any) {
    return wrap(chrome.runtime.sendMessage, msg);
}
