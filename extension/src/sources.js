/* @flow */

/*
 * In addition to sources indexed on the backend, some stuff lives inside the browser, e.g. local history + bookmarks
 */


import type {Url, AwareDate, NaiveDate} from './common'
import {Visit, Visits} from './common'
import {backend, getBackendVisits} from './api'
import {THIS_BROWSER_TAG} from './options'
import {normalise_url} from './normalise'
import type {HistoryItem} from './async_chrome'
import {achrome} from './async_chrome'


function getDelayMs(/*url*/) {
    return 10 * 1000;
}


// todo how to keep these deltas in sync with the backend?
const DELTA_BACK_S  = 3 * 60 * 60 // 3h
const DELTA_FRONT_S = 2 * 60      // 2min


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

        // NOTE: this normalise won't necessarily be the same as backend's... not sure what we can do about it without sending visits?
        const nurl = normalise_url(url)

        // NOTE: visitTime returns UTC epoch,
        const times: Array<Date> = results
            .map(r => new Date(r['visitTime'] || 0.0))
            .filter(dt => now - dt > delay)
        const visits = times.map(t => new Visit(
            url,
            nurl,
            ((t: any): AwareDate),
            ((t: any): NaiveDate), // there is no TZ info in history anyway, so not much else we can do
            [THIS_BROWSER_TAG],
        ))
        return new Visits(url, nurl, visits)
    },
    // TODO hmm I guess it's not necessarily searching url? any text
    search: async function(url: Url): Promise<Visits> {
        // TODO merge with actual visits for exact match?
        const android = await isAndroid()
        if (android) {
            return new Visits(url, url, [])
        }
        const nurl = normalise_url(url)
        const results = await achrome.history.search({text: url})
        const visits = []
        for (const r of results) {
            const u = r.url
            const ts = r.lastVisitTime
            if (u == null || ts == null) {
                continue
            }
            const t = new Date(ts)
            visits.push(new Visit(
                u,
                normalise_url(u),
                ((t: any): AwareDate),
                ((t: any): NaiveDate),
                [THIS_BROWSER_TAG],
                // TODO need context?
            ))
        }
        return new Visits(url, nurl, visits)
    },
    searchAround: async function(utc_timestamp_s: number): Promise<Visits> {
        const durl  = 'http://dummy.xyz'
        const ndurl = normalise_url(durl)
        const android = await isAndroid()
        if (android) {
            return new Visits(durl, ndurl, [])
        }
        const results = await achrome.history.search({
            // NOTE: I checked and it does seem like this method takes UTC epoch (although not clear from the docs)
            // note: it wants millis
            startTime: (utc_timestamp_s - DELTA_BACK_S ) * 1000,
            endTime  : (utc_timestamp_s + DELTA_FRONT_S) * 1000,
            text: '',
        })
        // TODO shit. displayed visit times are gonna be wrong because
        // only lastVisitTime is available... shit. maybe use in conjunction with getVisits and filter??
        // https://developer.chrome.com/extensions/history#type-HistoryItem
        // todo it also has maxResults? (default 100), not sure what should I do about it
        return new Visits(durl, ndurl, Array.from(history2visits(results)))
    }
}

function* history2visits(hi: Iterable<HistoryItem>) {
    for (const r of hi) {
        const u = r.url
        const ts = r.lastVisitTime
        if (u == null || ts == null) {
            continue
        }
        const t = new Date(ts)
        yield new Visit(
            u,
            normalise_url(u),
            ((t: any): AwareDate),
            ((t: any): NaiveDate),
            [THIS_BROWSER_TAG],
            // TODO need context?
        )
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


// todo take in from_, to?
function* bookmarks2visits(bit: Iterable<Bres>) {
    for (const {bm: r, nurl: nu, path: path} of bit) {
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
        yield new Visit(
            u,
            nu,
            ((t: any): AwareDate),
            ((t: any): NaiveDate),
            ['bookmark'],
            r.title,
            {title: path, href: null},
        )
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
        const all = bookmarksContaining(nurl, root, null)
        const visits = Array.from(bookmarks2visits(all))
        return new Visits(url, nurl, visits)
    },

    search: async function(url: Url): Promise<Visits> {
        // for bookmarks, search means the same as visits because they all come with context
        return (await bookmarks.visits(url))
    },

    searchAround: async function(utc_timestamp_s: number): Promise<Visits> {
        const durl = 'http://dummy.xyz'
        const ndurl = normalise_url(durl)
        if (await isAndroid()) {
            // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Browser_support_for_JavaScript_APIs#bookmarks :(
            return new Visits(durl, ndurl, [])
        }
        const root = (await achrome.bookmarks.getTree())[0]
        const all = bookmarksContaining('', root, null)
        // todo for the sake of optimization might be better to do this before building all the Visit objects..
        // same in visited method actually
        const back  = new Date((utc_timestamp_s - DELTA_BACK_S ) * 1000)
        const front = new Date((utc_timestamp_s + DELTA_FRONT_S) * 1000)
        const visits = []
        for (const v of bookmarks2visits(all)) {
            if (back <= v.time && v.time <= front) {
                visits.push(v)
            }
        }
        return new Visits(durl, ndurl, visits)
    },

    visited: async function(urls: Array<Url>): Promise<Array<boolean>> {
        if (await isAndroid()) {
            const res = new Array(urls.length)
            res.fill(false)
            return res
        }

        const root = (await achrome.bookmarks.getTree())[0]
        const allBookmarks = bookmarksContaining('', root, null)

        const nurls = new Set(Array.from(
            allBookmarks,
            ({bm: _bm, nurl: nurl, path: _path}) => nurl,
        ))

        return urls.map(u => nurls.has(normalise_url(u)))
    }
}


async function _merge(ra: Visits, b: Promise<Visits>, c: Promise<Visits>): Promise<Visits> {
    const rb = await b
    const rc = await c
    const merged = [
        ...ra.visits,
        ...rb.visits,
        ...rc.visits,
    ]
    return new Visits(
        ra.original_url,
        ra.normalised_url,
        merged,
    )
}

export const allsources = {
    /*
     * matches the exact url _or_ returns descendants with contexts
     * mainly used in the sidebar
     */
    visits: async function(url: Url): Promise<Visits | Error> {
        // TODO hmm. maybe have a special 'error' visit so we could just merge visits here?
        // it's gona be a mess though..
        const from_backend: Visits | Error = await getBackendVisits(url)
            .catch((err: Error) => err)

        // TODO def need to mixin and display all
        if (from_backend instanceof Error) {
            console.error('backend server request error: %o', from_backend)
            return from_backend
        }

        return _merge(
            from_backend,
            thisbrowser.visits(url),
            bookmarks  .visits(url)
        )
    },
    /*
     * ideally finds anything containing the query, used in search tab
     */
    search: async function(url: Url): Promise<Visits | Error> {
        const from_backend = await backend.search(url)
        if (from_backend instanceof Error) {
            console.error('backend server request error: %o', from_backend)
            return from_backend
        }
        return _merge(
            from_backend,
            thisbrowser.search(url),
            bookmarks  .search(url),
        )
    },
    searchAround: async function(utc_timestamp_s: number): Promise<Visits | Error> {
        const from_backend = await backend.searchAround(utc_timestamp_s)
        if (from_backend instanceof Error) {
            console.error('backend server request error: %o', from_backend)
            return from_backend
        }
        return _merge(
            from_backend,
            thisbrowser.searchAround(utc_timestamp_s),
            bookmarks  .searchAround(utc_timestamp_s),
        )
    },
    /*
     * for each url, returns a boolean -- whether or not the link was visited before
     * TODO would be cool to make it more iterative..
     */
    visited: async function(urls: Array<Url>): Promise<Array<boolean> | Error> {
        const from_backend = await backend.visited(urls)
        if (from_backend instanceof Error) {
            console.error('backend server request error: %o', from_backend)
            return from_backend
        }
        const res = from_backend
        const from_bookmarks = await bookmarks.visited(urls)
        for (let i = 0; i < urls.length; i++) {
            res[i] = res[i] || from_bookmarks[i]
        }
        // TODO hmm. unclear how to check it efficiently for browser history.. we'd need a query per URL
        // definitely would be nice to implement this iteratively instead.. so it could check in the background thread?
        // note: search with empty query will retrieve all? but def needs to be iterative then..
        return res
    },
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
