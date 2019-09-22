/* @flow */
import type {Url} from './common';
import {Blacklisted, lerror} from './common';
import {chromeTabsExecuteScriptAsync, chromeTabsInsertCSS} from './async_chrome';

// TODO common?
export function notify(message: string, priority: number=0) {
    chrome.notifications.create({
        'type'    : "basic",
        'title'   : "promnesia",
        'message' : message,
        'priority': priority,
        'iconUrl' : 'images/ic_not_visited_48.png',
    });
}

function errmsg(obj: any): string {
    let msg = null;
    if (obj instanceof XMLHttpRequest) {
        msg = `while requesting ${obj.responseURL}`;
    } else {
        msg = obj;
    }
    return `ERROR: ${msg}`;
}

export function notifyError(obj: any) {
    const message = errmsg(obj);
    lerror(obj);
    notify(message); // TODO maybe error icon or something?
}


export function alertError(obj: any) {
    const message = errmsg(obj);
    lerror(obj);
    alert(message);
}

export function defensify(pf: (...any) => Promise<any>, name: string=''): (any) => Promise<any> {
    return (...args) => pf(...args).catch((err) => {
        console.error('%s failed!', name);
        notifyError(err);
    });
}


export function defensifyAlert(pf: (...any) => Promise<any>): (any) => Promise<any> {
    return (...args) => pf(...args).catch(alertError);
}

export async function _showTabNotification(tabId: number, text: string, color: string='green') {
    // TODO can it be remote script?
    text = text.replace(/\n/g, "\\n"); // ....

    await chromeTabsExecuteScriptAsync(tabId, {file: 'toastify.js'});
    await chromeTabsInsertCSS(tabId, {file: 'toastify.css'});
    await chromeTabsExecuteScriptAsync(tabId, { code: `
Toastify({
  text: "${text}",
  duration: 2000,
  newWindow: true,
  close: true,
  gravity: "top",
  positionLeft: false,
  backgroundColor: "${color}",
}).showToast();
    ` });
}

// TODO maybe if tabId = -1, show normal notification?
// $FlowFixMe
export async function showTabNotification(tabId: number, message: string, ...args) {
    try {
        await _showTabNotification(tabId, message, ...args);
    } catch (error) {
        lerror(error);
        notifyError(message);
    }
}

export async function showIgnoredNotification(tabId: number, url: Url) {
    await showTabNotification(tabId, `${url} is ignored`, 'red'); // TODO maybe red is not ideal here
}

export async function showBlackListedNotification(tabId: number, b: Blacklisted) {
    await showTabNotification(tabId, `${b.url} is blacklisted: ${b.reason}`, 'red');
}
