import browser from "webextension-polyfill"

import type {Url} from './common'
import {Blacklisted} from './common'
import {getOptions} from './options'
import type {Options} from './options'


// last resort.. because these could be annoying (also might not make sense to display globally)
// only using it when there is no other context (e.g. current tab) to show a notification
export function desktopNotify(message: string, priority: number=0) {
    browser.notifications.create({
        'type'    : "basic",
        'title'   : "promnesia",
        'message' : message,
        'priority': priority,
        'iconUrl' : 'images/ic_not_visited_48.png',
    });
}


function error2string(err: Error): string {
    // sigh.. in chrome stack includes name and message already.. but not in firefox
    return `ERROR: ${err}\n${err.stack}`
}


export function notifyError(err: Error) {
    console.error(err)
    desktopNotify(error2string(err))
}


export function alertError(err: Error) {
    console.error(err)
    alert(error2string(err))
}


type DefensifyArgs = readonly unknown[]
export function defensify<Args extends DefensifyArgs>(
    pf: (...args: Args) => Promise<any>,
    name: string,
): (...args: Args) => Promise<void> {
    const fname = pf.name  // hopefully it's always present?
    const error_handler = (err: Error) => {
        console.error('function "%s" %s failed: %o', fname, name, err)
        getOptions().then((opts: Options) => {
            if (opts.verbose_errors_on) {
                notifyError(err)
            } else {
                console.warn("error notification is suppressed by 'verbose_errors' option")
            }
        })
    }
    return (...args: Args) => pf(...args).then(() => {
        // suppress return values, since the defensive error handler 'erases; the type anyway'
        return
    }).catch(error_handler)
}


type DefensifyAlertArgs = readonly unknown[]
export function defensifyAlert<Args extends DefensifyAlertArgs>(
    pf: (...args: Args) => Promise<any>,
): (...args: Args) => Promise<void> {
    return (...args) => pf(...args).catch(alertError)
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
async function showTabNotification(tabId: number | null, message: string, opts: ToastOptions): Promise<void> {
    if (tabId == null) {
        // not much else we can do..
        desktopNotify(message)
        return
    }
    try {
        await _showTabNotification(tabId, message, opts)
    } catch (error) {
        console.error('showTabNotification: %o %s', error, message)
        const errmsg = (error as Error).message || ''
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
    notify: async function(tabId: number | null, message: string, opts: ToastOptions): Promise<void> {
        return showTabNotification(tabId, message, opts)
    },
    error: async function(tabId: number, e: Error | string): Promise<void> {
        return notifications.notify(tabId, String(e), {color: 'red'})
    },
    page_ignored: async function(tabId: number | null, url: Url | null, reason: string): Promise<void> {
        return notifications.notify(tabId, `${url || ''} is ignored: ${reason}`, {color: 'red'})
    },
    excluded: async function(tabId: number, b: Blacklisted): Promise<void> {
        return notifications.notify(tabId, `${b.url} is excluded: ${b.reason}`, {color: 'red'})
    },
    desktop: desktopNotify,
}

// probably makes moresense as a name?
export const Notify = notifications
