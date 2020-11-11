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


type Bres = {
    bm: chrome$BookmarkTreeNode,
    nurl: Url,
    path: string,
}

// right, apparently there is no way to search bookmarks by prefix in webext apis..
// TODO need to be careful with performance..
function* bookmarksContaining(
    nurl: Url,
    cur: chrome$BookmarkTreeNode,
    path: ?string, // path in the bookmark tree
): Iterator<Bres> {
    const children = cur.children
    if (children == null) {
        return // shouldn't happen but makes flow happy anyway
    }
    for (const c of children) {
        const u = c.url
        if (u == null) {
            // must be folder?
            yield* bookmarksContaining(nurl, c, (path == null ? '' : path + ' :: ') + c.title)
        } else {
            const nu = normalise_url(u)
            if (nu.includes(nurl)) { // 'fuzzy' match
                yield {
                    bm: c,
                    nurl: nu,
                    path: (path == null ? '' : path),
                }
            }
        }
    }
}


// TODO need to test it
// TODO make togglable?
export const bookmarks = {
    // eh. not sure if this method is super useful, there is already 'star' indicator in most browsers
    // however it could benefit from the normalisation functionality
    visits: async function(url: Url): Promise<Visits> {
        if (await isAndroid()) {
            // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Browser_support_for_JavaScript_APIs#bookmarks :(
            return new Visits(url, url, [])
        }
        const nurl = normalise_url(url)
        const root = (await achrome.bookmarks.getTree())[0]
        const results = Array.from(bookmarksContaining(nurl, root, null))

        const visits = []
        for (const {bm: r, nurl: nu, path: path} of results) {
            const u = r.url
            if (u == null) {
                // shouldn't happen, but makes flow happy
                continue
            }
            const added = r.dateAdded
            if (added == null) {
                // why would it be?? but the docs say optional..
                continue
            }
            const t = new Date(added)
            visits.push(new Visit(
                u,
                nu,
                ((t: any): AwareDate),
                ((t: any): NaiveDate),
                ['bookmark'],
                r.title,
                {title: path, href: null},
            ))
        }
        return new Visits(url, nurl, visits)
    }
}

/*  to test bookmarks:
for (let i = 0; i < 100; i++) {
    chrome.bookmarks.create({
        url: `https://example.com/${i}.html`,
        title: `Example ${i}`,
    }, (res) => {
        console.log("CREATED %o", res)
    })
}
*/


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
