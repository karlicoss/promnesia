/* @flow */

/*
 * Communication with backend
 */


import type {Locator, Src, Url, Second, JsonObject, AwareDate, NaiveDate} from './common'
import {Visit, Visits} from './common'
import {getOptions} from './options'
import {normalise_url} from './normalise'


type VisitsResponse = {
    visits: Array<JsonObject>,
    original_url: string,
    normalised_url: string,
}

type VisitedResponse = Array<boolean>

export async function queryBackendCommon<R>(params: {}, endp: string): Promise<R | Error> {
    const opts = await getOptions()
    if (opts.host == '') { // use 'dummy' backend
        // the user only wants to use browser visits?
        // todo: won't work for all endpoints, but can think how to fix later..
        if (endp == 'visits' || endp == 'search' || endp == 'search_around') {
            // $FlowFixMe
            let url = params['url']
            if (url == null) { // meh need to be stricter here..
                url = 'http://TODO_FIXME.org'
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
            const res: VisitedResponse = new Array(urls.length)
            res.fill(false)
            return ((res: any): R)
        } else {
            throw new Error(`'${endp}' isn't implemented without the backend yet. Please set host in the extension settings.`)
        }
    }

    const endpoint = `${opts.host}/${endp}`
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
            throw new Error(`${response.statusText} (${response.status}`)
        }
        return response.json()
    }).catch((err: Error) => {
        const stack = []
        if (err.stack) {
            stack.push(err.stack)
        }
        stack.push(`while requesting ${endpoint}`)
        stack.push("check extension options, make sure you set backend or disable it (set to empty string)")
        err.stack = stack.join('\n')
        return err
    })
}

export async function getBackendVisits(u: Url): Promise<Visits | Error> {
    return queryBackendCommon<JsonObject>({url: u}, 'visits')
        .then(rawToVisits)
        .catch((err: Error) => err)
    // todo not sure if this error handling should be here?
}


// eslint-disable-next-line no-unused-vars
export function makeFakeVisits(count: number): Visits {
    const res = []
    const ref_ms = 1600000000 * 1000
    for (let i = 0; i < count; i++) {
        const  d = new Date(ref_ms + i * 1000)
        res.push(new Visit(
            `github.com/${i}`,
            `github.com/${i}`,
            ((d: any): AwareDate),
            ((d: any): NaiveDate),
            ['fake'],
            i < count / 3 ? null : `context ${i}`,
            null,
            null,
        ))
    }
    return new Visits(
        'github.com',
        'github.com',
        res,
    )
}


export const backend = {
    search: async function(url: Url): Promise<Visits | Error> {
        return await queryBackendCommon<JsonObject>({url: url}, 'search')
              .then(r => rawToVisits(r, url))
              .catch((err: Error) => err)
    },
    searchAround: async function(utc_timestamp_s: number): Promise<Visits | Error> {
        return await queryBackendCommon<JsonObject>({timestamp: utc_timestamp_s}, 'search_around')
               .then(rawToVisits)
               .catch((err: Error) => err)
    },
    visited: async function(urls: Array<Url>): Promise<VisitedResponse | Error> {
        return await queryBackendCommon<Array<boolean>>({urls: urls}, 'visited')
               .catch((err: Error) => err)
    },
}

function rawToVisits(vis: VisitsResponse | Error, url='http://shouldnothappen.xyz'): Visits | Error {
    if (vis instanceof Error) {
        // most likely, network error.. so handle it defensively
        return new Visits(url, url, [vis])
    }
    // TODO filter errors? not sure.
    const visits = vis['visits'].map(v => {
        const dts = v['dt']
        // NOTE: server returns a string with TZ offset
        // Date class in js always keeps UTC inside
        // so we just use two separate values and treat them differently
        const dt_utc   = ((new Date(dts)                           : any): AwareDate)
        const dt_local = ((new Date(dts.slice(0, -' +0000'.length)): any): NaiveDate)
        const vtags: Array<Src> = [v['src']]; // todo hmm. shouldn't be array?
        const vourl: string = v['original_url'];
        const vnurl: string = v['normalised_url'];
        const vctx: ?string = v['context'];
        const vloc: ?Locator = v['locator']
        const vdur: ?Second = v['duration'];
        return new Visit(vourl, vnurl, dt_utc, dt_local, vtags, vctx, vloc, vdur);
    });
    return new Visits(
        vis['original_url'],
        vis['normalised_url'],
        visits
    );
}
