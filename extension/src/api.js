/* @flow */

/*
 * Communication with backend
 */


import type {Locator, Src, Url, Second, JsonObject, AwareDate, NaiveDate} from './common'
import {unwrap, Visit, Visits} from './common'
import {getOptions} from './options'
import {normalise_url} from './normalise'


type VisitsResponse = {
    visits: Array<JsonObject>,
    original_url: string,
    normalised_url: string,
}

// NOTE: boolean is legacy behaviour
type VisitedBackendResponse = Array<?JsonObject | boolean>

// TODO ugh, why params: {} not working??
export async function queryBackendCommon<R>(params: any, endp: string): Promise<R | Error> {
    const opts = await getOptions()
    if (opts.host == '') { // use 'dummy' backend
        // the user only wants to use browser visits?
        // todo: won't work for all endpoints, but can think how to fix later..
        if (endp == 'visits' || endp == 'search' || endp == 'search_around') {
            // $FlowFixMe
            let url = params['url']
            if (url == null) { // meh need to be stricter here..
                url = 'http://DUMMYURL.org'
            }
            const res: VisitsResponse = {
                visits: [],
                original_url: url,
                normalised_url: normalise_url(url),
            }
            return ((res: any): R)
        } else if (endp == 'visited') {
            // $FlowFixMe
            let urls: Array<Url> = params['urls']
            const res: VisitedBackendResponse = new Array(urls.length)
            res.fill(null)
            return ((res: any): R)
        } else {
            throw new Error(`'${endp}' isn't implemented without the backend yet. Please set host in the extension settings.`)
        }
    }

    const endpoint = `${opts.host}/${endp}`
    params['client_version'] = chrome.runtime.getManifest().version

    function with_stack(e: Error): Error {
        const stack = []
        if (e.stack) {
            stack.push(e.stack)
        }
        stack.push(`while requesting ${endpoint}`)
        stack.push("check extension options, make sure you set backend or disable it (set to empty string)")
        e.stack = stack.join('\n')
        console.error(e, e.stack) // hopefully worth loging, meant to happen rarely
        return e
    }

    // TODO cors mode?
    return fetch(endpoint, {
        method: 'POST', // todo use GET?
        headers: {
            'Content-Type' : 'application/json',
            'Authorization': "Basic " + btoa(opts.token),
        },
        body: JSON.stringify(params)
    }).then(response => {
        // right, fetch API doesn't reject on HTTP error status...
        const ok = response.ok
        if (!ok) {
            return with_stack(new Error(`${response.statusText} (${response.status}`))
        }
        return response.json()
    }).catch((err: Error) => {
        return with_stack(err)
    })
}

// eslint-disable-next-line no-unused-vars
export function makeFakeVisits(count: number): Visits {
    return new Visits(
        'github.com',
        'github.com',
        fake.apiVisits(count).map(v => unwrap(rawToVisit(v))),
    )
}


export const backend = {
    visits: async function(url: Url): Promise<Visits | Error> {
        return await queryBackendCommon<JsonObject>({url: url}, 'visits')
              .then(rawToVisits)
              .catch((err: Error) => err)
        // todo not sure if this error handling should be here?
    },
    search: async function(url: Url): Promise<Visits | Error> {
        return await queryBackendCommon<JsonObject>({url: url}, 'search')
              .then(rawToVisits)
              .catch((err: Error) => err)
    },
    searchAround: async function(utc_timestamp_s: number): Promise<Visits | Error> {
        return await queryBackendCommon<JsonObject>({timestamp: utc_timestamp_s}, 'search_around')
               .then(rawToVisits)
               .catch((err: Error) => err)
    },
    visited: async function(urls: Array<Url>): Promise<Array<?Visit> | Error> {
        return await queryBackendCommon<VisitedBackendResponse>({urls: urls}, 'visited')
            .then(r => {
                if (r instanceof Error) {
                    return r
                }
                const res: Array<?Visit> = new Array(r.length)
                res.fill(null)
                const now = new Date() // TODO hmm, need to think of smth better?
                for (let i = 0; i < r.length; i++) {
                    let x: ?JsonObject | boolean = r[i]
                    if (x == null) {
                        res[i] = null
                        continue
                    }
                    let url = urls[i]
                    let v: ?Visit
                    if (typeof x === "boolean") {
                        // legavy behaviour
                        if (x === false) {
                            v = null
                        } else {
                            v = new Visit(
                                url,
                                normalise_url(url),
                                ((now: any): AwareDate),
                                ((now: any): NaiveDate),
                                ['backend'], // TODO suggest to update the backend?
                            )
                        }
                    } else {
                        // visit already?
                        v = rawToVisit(x)
                    }
                    res[i] = v
                }
                return res
            })
            .catch((err: Error) => err)
    },
}

function rawToVisits(vis: VisitsResponse | Error): Visits | Error {
    if (vis instanceof Error) {
        // most likely, network error.. so handle it defensively
        return vis
    }
    // TODO filter errors? not sure.
    // TODO this could be more defensive too
    const visits = vis['visits'].map(x => unwrap(rawToVisit(x)))
    return new Visits(
        vis['original_url'],
        vis['normalised_url'],
        visits
    )
}

function rawToVisit(v: ?JsonObject): ?Visit {
    if (v == null) {
        return null
    }
    const dts = v['dt']
    // NOTE: server returns a string with TZ offset
    // Date class in js always keeps UTC inside
    // so we just use two separate values and treat them differently
    const dt_utc   = ((new Date(dts)                           : any): AwareDate)
    let dtl = new Date(dts.slice(0, -' +0000'.length))
    // ugh. parsing doesn't even throw?
    if (isNaN(dtl.getTime())) {
        console.error('error parsing %s', dts)
        dtl = new Date(dts)
    }
    const dt_local = ((dtl: any): NaiveDate)
    const vtags: Array<Src> = [v['src']] // todo hmm. shouldn't be array?
    const vourl: string = v['original_url']
    const vnurl: string = v['normalised_url']
    const vctx: ?string = v['context']
    const vloc: ?Locator = v['locator']
    const vdur: ?Second = v['duration']
    return new Visit(vourl, vnurl, dt_utc, dt_local, vtags, vctx, vloc, vdur)
}


export const fake = {
    apiVisits: function(count: number): Array<JsonObject> {
        const res = []
        const ref_s = 1600000000
        for (let i = 0; i < count; i++) {
            res.push({
                original_url  : `http://github.com/${i}/`,
                normalised_url: `github.com/${i}`,
                dt      : new Date((ref_s + i) * 1000).toISOString(),
                src     : 'fake',
                context : i < count / 3 ? null : `context ${i}`,
                locator : null,
                duration: null,
            })
        }
        return res
    }
}
