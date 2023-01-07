/* @flow */
import type {Url} from './common';
import {Blacklisted} from './common';
import {getOptions} from './options';


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


export function defensify(pf: (...any) => Promise<any>, name: string): (...any) => Promise<void> {
    const fname = pf.name // hopefully it's always present?
    const error_handler = (err: Error) => {
        console.error('function "%s" %s failed: %o', fname, name, err)
        getOptions().then(opts => {
            if (opts.verbose_errors_on) {
                notifyError(err, 'defensify')
            } else {
                console.warn("error notification is suppressed by 'verbose_errors' option")
            }
        })
    }
    return (...args) => pf(...args).then(() => {
        // suppress return values, since the defensive error handler 'erases; the type anyway'
        return
    }).catch(error_handler)
}


// TODO return type should be void here too...
export function defensifyAlert(pf: (...any) => Promise<any>): (any) => Promise<any> {
    return (...args) => pf(...args).catch(alertError);
}


type ToastOptions = {
    color?: string,
    duration_ms?: number,
}

export async function _showTabNotification(tabId: number, text: string, {color: color, duration_ms: duration_ms}: ToastOptions) {
    color = color || 'green'
    duration_ms = duration_ms || 2 * 1000
    // TODO can it be remote script?
    text = text.replace(/\n/g, "\\n"); // ....

    await browser.tabs.executeScript(tabId, {file: 'toastify.js'})
    await browser.tabs.insertCSS(tabId, {file: 'toastify.css'});
    // TODO extract toast settings somewhere...
    await browser.tabs.executeScript(tabId, { code: `
Toastify({
  text: "${text}",
  duration: ${duration_ms},
  newWindow: true,
  close: true,
  stopOnFocus: true, // prevent dismissing on hover
  gravity: "top",
  positionLeft: false,
  backgroundColor: "${color}",
}).showToast();
    ` });
    // todo ugh. close icon is shown on the bottom?..
}

// TODO maybe if tabId = -1, show normal notification?
async function showTabNotification(tabId: ?number, message: string, opts: ToastOptions): Promise<void> {
    if (tabId == null) {
        // not much else we can do..
        desktopNotify(message)
        return
    }
    try {
        await _showTabNotification(tabId, message, opts)
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
    notify: async function(tabId: ?number, message: string, opts: ToastOptions): Promise<void> {
        return showTabNotification(tabId, message, opts)
    },
    error: async function(tabId: number, e: Error | string): Promise<void> {
        return notifications.notify(tabId, String(e), {color: 'red'})
    },
    page_ignored: async function(tabId: ?number, url: ?Url, reason: string): Promise<void> {
        return notifications.notify(tabId, `${url || ''} is ignored: ${reason}`, {color: 'red'})
    },
    excluded: async function(tabId: number, b: Blacklisted): Promise<void> {
        return notifications.notify(tabId, `${b.url} is excluded: ${b.reason}`, {color: 'red'})
    },
    desktop: desktopNotify,
}

// probably makes moresense as a name?
export const Notify = notifications
