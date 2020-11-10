/* @flow */
import type {Locator, Src, Url, Second, JsonObject, AwareDate, NaiveDate} from './common'
import {Visit, Visits} from './common'
import {getOptions} from './options'


export async function queryBackendCommon<R>(params: {}, endp: string): Promise<R> {
    const opts = await getOptions()
    if (opts.host == '') {
        // the user only wants to use browser visits?
        // todo: won't work for all endpoints, but can think how to fix later..
        if (endp == 'visits') {
            return (({visits: []} : any): R)
        } else {
            throw Error(`'${endp}' isn't implemented without the backend yet. Please set host in the extension settings.`)
        }
    }

    const endpoint = `${opts.host}/${endp}`;
    // TODO cors mode?
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type' : 'application/json',
            'Authorization': "Basic " + btoa(opts.token),
        },
        body: JSON.stringify(params)
    }).then(response => {
        // right, fetch API doesn't reject on HTTP error status...
        const ok = response.ok;
        if (!ok) {
            throw Error(response.statusText + ' (' + response.status + ')');
        }
        return response.json();
    });
    return response;
}

export async function getBackendVisits(u: Url): Promise<Visits> {
    return queryBackendCommon<JsonObject>({url: u}, 'visits').then(rawToVisits);
}


// eslint-disable-next-line no-unused-vars
function makeFakeVisits(count: number): Visits {
    const res = []
    const ref_ms = 1600000000 * 1000
    for (let i = 0; i < count; i++) {
        const  d = new Date(ref_ms + i * 1000)
        res.push(new Visit(
            `github.com/${i}`,
            `github.com/${i}`,
            ((d: any): AwareDate),
            ((d: any): NaiveDate),
            [],
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

// TODO include browser visits here too?
// see https://github.com/karlicoss/promnesia/issues/120
export async function searchVisits(u: Url): Promise<Visits> {
    return queryBackendCommon<JsonObject>({url: u}, 'search').then(rawToVisits);
}

export async function searchAround(timestamp: number): Promise<Visits> {
    return queryBackendCommon<JsonObject>({timestamp: timestamp}, 'search_around').then(rawToVisits);
}


function rawToVisits(vis: JsonObject): Visits {
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
