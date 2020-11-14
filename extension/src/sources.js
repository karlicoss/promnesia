/* @flow */

/*
 * In addition to sources indexed on the backend, some stuff lives inside the browser, e.g. local history + bookmarks
 */

/*
 * Error handling strategy for individual data sources
 * - if it's a critical error (network/deserialising/etc/just programming error), propagate it up as Error
 * - if it's an individual item that's failed, put in in the Visits as Error
 *
 * TODO after that would be kinda nice to tell apart critical and non-critical errors?
 * but unclear how, typing doesn't really help here..
 * for now it's all just squashed into Visits.. but later might reconsider
 */

import type {Url, AwareDate, NaiveDate} from './common'
import {Visit, Visits} from './common'
import {backend} from './api'
import {THIS_BROWSER_TAG, getOptions} from './options'
import {normalise_url} from './normalise'
import type {HistoryItem} from './async_chrome'
import {achrome} from './async_chrome'


function getDelayMs(/*url*/) {
    return 10 * 1000;
}


// todo how to keep these deltas in sync with the backend?
const DELTA_BACK_S  = 3 * 60 * 60 // 3h
const DELTA_FRONT_S = 2 * 60      // 2min


// can be false, if no associated visits, otherwise true or an actual Visit if it's available
type VisitedResult = Array<boolean | Visit>

// TODO eh, confusing that we have backend sources.. and these which are also sources, at the same time
interface VisitsSource {
    visits(url: Url)                     : Promise<Visits | Error>,
    search(url: Url)                     : Promise<Visits | Error>,
    searchAround(utc_timestamp_s: number): Promise<Visits | Error>,
    visited(urls: Array<Url>)            : Promise<VisitedResult | Error>,
}


function* search2visits(it: Iterable<HistoryItem>): Iterator<Visit> {
    for (const r of it) {
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

// NOTE: do not name this 'browser', it might be a builtin for apis (alias to 'chrome')
export const thisbrowser: VisitsSource = {
// TODO async iterator?
    visits: async function(url: Url): Promise<Visits | Error> {
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
    search: async function(url: Url): Promise<Visits | Error> {
        // TODO merge with actual visits for exact match?
        const android = await isAndroid()
        if (android) {
            return new Visits(url, url, [])
        }
        const nurl = normalise_url(url)
        const results = await achrome.history.search({text: url})
        const visits = Array.from(search2visits(results))
        return new Visits(url, nurl, visits)
    },
    searchAround: async function(utc_timestamp_s: number): Promise<Visits | Error> {
        const durl  = 'http://dummy.xyz'
        const ndurl = normalise_url(durl)
        const android = await isAndroid()
        if (android) {
            return new Visits(durl, ndurl, [])
        }
        const start = (utc_timestamp_s - DELTA_BACK_S ) * 1000
        const end   = (utc_timestamp_s + DELTA_FRONT_S) * 1000
        const results = await achrome.history.search({
            // NOTE: I checked and it does seem like this method takes UTC epoch (although not clear from the docs)
            // note: it wants millis
            startTime: start,
            endTime  : end,
            text: '',
            // todo it also has maxResults? (default 100), not sure what should I do about it
        })
        // right. this only returns history items with lastVisitTime
        // (see https://developer.chrome.com/extensions/history#type-HistoryItem)
        // so we need another pass to collec the 'correct' visit times
        const visits = []
        for (const r of results) {
            const u = r.url
            if (u == null) {
                continue
            }
            const nu = normalise_url(u)
            // eh. apparently URL is the only useful?
            for (const v of await achrome.history.getVisits({url: u})) {
                const vt = v.visitTime || 0.0
                if (start <= vt && vt <= end) {
                    const t = new Date(vt)
                    visits.push(new Visit(
                        u,
                        nu,
                        ((t: any): AwareDate),
                        ((t: any): NaiveDate),
                        [THIS_BROWSER_TAG],
                    ))
                }
            }
        }
        return new Visits(durl, ndurl, visits)
    },
    visited: async function(urls: Array<Url>): Promise<VisitedResult | Error> {
        // TODO hmm. unclear how to check it efficiently for browser history.. we'd need a query per URL
        // definitely would be nice to implement this iteratively instead.. so it could check in the background thread?
        // note: search with empty query will retrieve all? but def needs to be iterative then..
        // ok, for now as a compromise, query 1000 latest visits..
        const res = await achrome.history.search({
            maxResults: 1000,
            text: '',
        })
        const map: Map<Url, Visit> = new Map()
        for (const v of search2visits(res)) {
            const nurl = v.normalised_url
            if (!map.has(nurl)) {
                map.set(nurl, v)
            }
        }
        // todo might be useful to pass in normalised urls in this method?
        return urls.map(u => map.get(normalise_url(u)) || false)
    },
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

export const bookmarks: VisitsSource = {
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

    search: async function(url: Url): Promise<Visits | Error> {
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

    visited: async function(urls: Array<Url>): Promise<VisitedResult | Error> {
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

        // todo normalised url might be worth a separate type..
        return urls.map(u => nurls.has(normalise_url(u)))
    }
}


async function _merge(url: ?string, ...args: Array<Promise<Visits | Error>>): Promise<Visits | Error> {
    let rurl  = null
    let rnurl = null
    const parts = []
    for (const p of args) {
        const r = await p.catch(
            (e: Error) => {
                // some hardcode defesiveness
                // but justified in webext..
                console.error(e)
                return e
            },
        )
        if (r instanceof Error) {
            parts.push([r])
        } else {
            if (rurl == null) {
                // generally, prefer whatever backend has returned
                rurl  = r.original_url
                rnurl = r.normalised_url
            }
            parts.push(r.visits)
        }
    }
    if (rurl == null || rnurl == null) {
        rurl  = url || 'http://ERROR.ERROR' // last resort measure
        rnurl = normalise_url(rurl)
    }
    return new Visits(
        rurl,
        rnurl,
        [].concat(...parts),
    )
}


export class MultiSource implements VisitsSource {
    // todo just move all methods from allsources inside like search
    sources: Array<VisitsSource>;
    constructor(...sources: Array<VisitsSource>) {
        this.sources = sources
    }

    async visits(url: Url) {
        return await _merge(url, ...this.sources.map(s => s.visits(url)))
    }

    async search(url: Url) {
        return await _merge(url, ...this.sources.map(s => s.search(url)))
    }

    async searchAround(utc_timestamp_s: number) {
        return await _merge(null, ...this.sources.map(s => s.searchAround(utc_timestamp_s)))
    }

    async visited(urls: Array<Url>) {
        const pms = this.sources.map(s => s.visited(urls))
        const errors = []
        let res: ?VisitedResult = null
        for (const p of pms) {
            const r = await p.catch((e: Error) => e)
            if (r instanceof Error) {
                errors.push(r)
            } else {
                if (res == null) {
                    res = r
                } else {
                    for (let i = 0; i < urls.length; i++) {
                        const a = res[i]
                        if (a instanceof Visit) {
                            // todo later maybe return multiple visits associated with a link? might have a performance impact..
                            continue
                        }
                        const b = r[i]
                        if (b instanceof Visit) {
                            res[i] = b
                            continue
                        }
                        res[i] = a || b
                    }
                }
            }
        }
        // TODO later when I support some sidebar info for this method, propagate errors properly...
        if (res != null) {
            return res
        }
        if (errors.length > 0) {
            return errors[0]
        }
        return new Error("No datasources?")
    }

    static async get(): Promise<MultiSource> {
        const opts = await getOptions()
        const srcs = []
        if (opts.host != '') {
            srcs.push(backend)
        }
        if (opts.use_bookmarks) {
            srcs.push(bookmarks)
        }
        if (opts.use_browserhistory) {
            srcs.push(thisbrowser)
        }
        // TODO error when no sources used??
        return new MultiSource(...srcs)
    }
}


export const allsources = {
    /*
     * matches the exact url _or_ returns descendants with contexts
     * mainly used in the sidebar
     */
    visits: async function(url: Url): Promise<Visits | Error> {
        return (await MultiSource.get()).visits(url)
    },
    /*
     * ideally finds anything containing the query, used in search tab
     */
    search: async function(url: Url): Promise<Visits | Error> {
        return (await MultiSource.get()).search(url)
    },
    searchAround: async function(utc_timestamp_s: number): Promise<Visits | Error> {
        return (await MultiSource.get()).searchAround(utc_timestamp_s)
    },
    /*
     * for each url, returns a boolean -- whether or not the link was visited before
     * TODO would be cool to make it more iterative..
     */
    visited: async function(urls: Array<Url>): Promise<VisitedResult | Error> {
        return (await MultiSource.get()).visited(urls)
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
