/* @flow */
import type {Url} from './common';
import {Blacklisted} from './common';
import {getOptions} from './options';
import {achrome} from './async_chrome'


// last resort.. because these could be annoying (also might not make sense to display globally)
// only using it when there is no other context (e.g. current tab) to show a notification
export function desktopNotify(message: string, priority: number=0) {
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

export function notifyError(obj: any, context: string='') {
    const message = errmsg(obj);
    console.error('%o, context=%s', obj, context);
    desktopNotify(message)
}


export function alertError(obj: any) {
    const message = errmsg(obj);
    console.error('%o', obj);
    alert(message);
}

export function defensify(pf: (...any) => Promise<any>, name: string): (any) => Promise<any> {
    const fname = pf.name // hopefully it's always present?
    return (...args) => pf(...args).catch((err) => {
        console.error('function "%s" %s failed: %o', fname, name, err);
        getOptions().then(opts => {
            if (opts.verbose_errors_on) {
                notifyError(err, 'defensify');
            } else {
                console.warn("error notification is suppressed by 'verbose_errors' option");
            }
        });
    });
}


export function defensifyAlert(pf: (...any) => Promise<any>): (any) => Promise<any> {
    return (...args) => pf(...args).catch(alertError);
}

export async function _showTabNotification(tabId: number, text: string, color: string='green') {
    // TODO can it be remote script?
    text = text.replace(/\n/g, "\\n"); // ....

    await achrome.tabs.executeScript(tabId, {file: 'toastify.js'})
    await achrome.tabs.insertCSS(tabId, {file: 'toastify.css'});
    // TODO extract toast settings somewhere...
    await achrome.tabs.executeScript(tabId, { code: `
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
export async function showTabNotification(tabId: ?number, message: string, ...args: Array<any>) {
    if (tabId == null) {
        // not much else we can do..
        desktopNotify(message)
        return
    }
    try {
        await _showTabNotification(tabId, message, ...args)
    } catch (error) {
        console.error('showTabNotification: %o %s', error, message)
        let errmsg = error.message || ''
            // ugh. might happen if the page is down..
        if (errmsg.includes('Missing host permission for the tab') ||
            // might happen on special pages?
            errmsg.includes('Extension manifest must request permission to access this host')
        ) {
            // in that case it doesn't have the context to show a popup.
            // could make it configurable??
            // tested by test_unreachable
            desktopNotify(message)
        } else {
            throw error
        }
    }
}

export const notifications = {
    error: async function(tabId: number, e: Error) {
        await showTabNotification(tabId, e.toString(), 'red')
    },
    page_ignored: async function(tabId: ?number, url: ?Url, reason: string) {
        await showTabNotification(tabId, `${url || ''} is ignored: ${reason}`, 'red')
    },
    blacklisted: async function(tabId: number, b: Blacklisted) {
        await showTabNotification(tabId, `${b.url} is blacklisted: ${b.reason}`, 'red')
    }
}
