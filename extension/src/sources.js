/* @flow */

/*
 * In addition to sources indexed on the backend, some stuff lives inside the browser, e.g. local history + bookmarks
 */


import type {Url, AwareDate, NaiveDate} from './common'
import {Visit, Visits} from './common'
import {THIS_BROWSER_TAG} from './options'
import {normalise_url} from './normalise'
import {achrome} from './async_chrome'


function getDelayMs(/*url*/) {
    return 10 * 1000;
}


// NOTE: do not name this 'browser', it might be a builtin for apis (alias to 'chrome')
export const thisbrowser = {
// TODO async iterator?
    visits: async function(url: Url): Promise<Visits> {
        const android = await isAndroid()
        if (android) {
            // ugh. 'history' api is not supported on mobile (TODO mention that in readme)
            // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Differences_between_desktop_and_Android#Other_UI_related_API_and_manifest.json_key_differences
            return new Visits(url, url, [])
        }

        const results = await achrome.history.getVisits({url: url})

        // without delay you will always be seeing website as visited
        // TODO but could be a good idea to make it configurable; e.g. sometimes we do want to know immediately. so could do domain-based delay or something like that?
        const delay = getDelayMs()
        const now = new Date()

        // NOTE: visitTime returns UTC epoch,
        const times: Array<Date> = results
            .map(r => new Date(r['visitTime']))
            .filter(dt => now - dt > delay)
        const visits = times.map(t => new Visit(
            url,
            // NOTE: this normalise won't necessarily be the same as backend's... not sure what we can do about it without sending visits?
            normalise_url(url),
            ((t: any): AwareDate),
            ((t: any): NaiveDate), // there is no TZ info in history anyway, so not much else we can do
            [THIS_BROWSER_TAG],
        ))
        return new Visits(url, url, visits)
    }
}


export const bookmarks = {
    // eh. not sure if this method is super useful, there is already 'star' indicator in most browsers
    // however it could benefit from the normalisation functionality
    visits: async function(url: Url): Promise<Visits> {
        if (await isAndroid()) {
            // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Browser_support_for_JavaScript_APIs#bookmarks :(
            return new Visits(url, url, [])
        }
      
        // NOTE: this url: results in exact match..
        // might want to have a more fuzzy version, especially for child visits
        const results = await achrome.bookmarks.search({url: url})

        const visits = []
        for (const r of results) {
            if (r.url == null) {
                // must be folder
                continue
            }
            const added = r.dateAdded
            if (added == null) {
                // why would it be?? but the docs say optional..
                continue
            }
            const t = new Date(added)
            visits.push(new Visit(
                url,
                normalise_url(url),
                ((t: any): AwareDate),
                ((t: any): NaiveDate),
                ['bookmark'],
                r.title,
                // todo not sure what could be a locator? path to the parent?
            ))
        }
        return new Visits(url, normalise_url(url), visits)
    }
}


export async function isAndroid(): Promise<boolean> {
    try {
        const platform = await achrome.runtime.getPlatformInfo()
        return platform.os === 'android'
    } catch (error) {
        // defensive just in case since isAndroid is kinda crucial for extension functioning
        console.error('error while determining platfrom; assuming not android: %o', error)
        return false
    }
}
