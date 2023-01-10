/* @flow */

export type Url = string;
export type Src = string;
export type Second = number;
export type Locator = {
    title: string,
    href: ?string,
};
export type VisitsMap = {[Url]: Visits};
export type Dt = Date;

export opaque type AwareDate: Date = Date;
export opaque type NaiveDate: Date = Date;

export function unwrap<T>(x: ?T): T {
    if (x == null) {
        console.trace("undefined or null")  // print trace as well, so it's easier to find out what was null
        throw new Error("undefined or null!")
    }
    return x
}


export function format_duration(seconds: Second): string {
    let s = seconds;
    if (s < 60) {
        return `${s} seconds`
    }
    // forget seconds otherwise and just use days/hours/minutes
    s = Math.floor(s / 60);
    let parts = [];
    const hours = Math.floor(s / 60);
    s %= 60;
    if (hours > 0) {
        parts.push(`${hours} hours`);
    }
    parts.push(`${s} minutes`);
    return parts.join(" ");
}

// TODO just use object
export class Visit {
    original_url: string;
    normalised_url: string;
    /* NOTE: Date class in JS is always keeping the date in UTC (even though when displayed it's converted to browser's TZ)
     * so we workaround this by keeping both...
     */
    time: AwareDate; // TODO rename to dt_utc?
    dt_local: NaiveDate;

    tags: Array<Src>; // TODO need to rename tags to sources
    context: ?string;
    locator: ?Locator;
    duration: ?Second;


    constructor(original_url: string, normalised_url: string, time: AwareDate, dt_local: NaiveDate, tags: Array<Src>, context: ?string=null, locator: ?Locator=null, duration: ?Second=null) {
        this.original_url   = original_url;
        this.normalised_url = normalised_url;
        this.time     = time;
        this.dt_local = dt_local;
        this.tags = tags;
        this.context = context;
        this.locator = locator;
        this.duration = duration;
    }

    // ugh..
    toJObject(): any {
        const o = {}
        // $FlowFixMe[prop-missing]
        Object.assign(o, this)
        // $FlowFixMe
        o.time     = o.time    .getTime()
        // $FlowFixMe
        o.dt_local = o.dt_local.getTime()
        return o
    }

    static fromJObject(o: any): Visit {
        o.time     = new Date(o.time)
        o.dt_local = new Date(o.dt_local)
        // $FlowFixMe
        const v = new Visit()
        // $FlowFixMe[prop-missing]
        Object.assign(v, o)
        return v
    }
}

type VisitsList = Array<Visit | Error>
// TODO errors might have datetime?

export class Visits {
    original_url  : Url
    normalised_url: Url
    // TODO might be better to have a single list with Visit | Error type?
    visits: VisitsList

    constructor(original_url: Url, normalised_url: Url, visits: VisitsList) {
        this.original_url = original_url;
        this.normalised_url = normalised_url;
        this.visits = visits;
    }

    partition(): [Array<Visit>, Array<Error>] {
        const good  = []
        const err   = []
        for (const r of this.visits) {
            if (r instanceof Visit) {
                good.push(r)
            } else {
                err.push(r)
            }
        }
        return [good, err]
    }

    self_contexts(): Array<?Locator> {
        const locs = [];
        for (const visit of this.partition()[0]) {
            if (visit.context === null) {
                continue;
            }
            if (visit.normalised_url == this.normalised_url) {
                locs.push(visit.locator);
            }
        }
        return locs;
    }
    relative_contexts(): Array<?Locator> {
        const locs = [];
        for (const visit of this.partition()[0]) {
            if (visit.context === null) {
                continue;
            }
            if (visit.normalised_url != this.normalised_url) {
                locs.push(visit.locator);
            }
        }
        return locs;
    }

    // NOTE: JSON.stringify will use this method
    toJObject(): any {
        const o = {}
        // $FlowFixMe[prop-missing]
        Object.assign(o, this)
        // $FlowFixMe[prop-missing]
        // $FlowFixMe[incompatible-use]
        o.visits = o.visits.map(v => {
            return (v instanceof Visit)
                ? v.toJObject()
                // $FlowFixMe
                : {error: v.message, stack: v.stack}
        })
        return o
    }

    static fromJObject(o: any): Visits {
        // $FlowFixMe[prop-missing]
        o.visits = o.visits.map(x => {
            const err = x.error
            if (err != null) {
                const e = new Error(err)
                // todo preserve name?
                e.stack = x.stack
                return e
            } else {
                return Visit.fromJObject(x)
            }
        })
        // $FlowFixMe[prop-missing]
        // $FlowFixMe
        const r = new Visits()
        // $FlowFixMe[prop-missing]
        Object.assign(r, o)
        return r
    }
}

export class Blacklisted {
    url: Url;
    reason: string;

    constructor(url: Url, reason: string) {
        this.url = url;
        this.reason = reason;
    }
}

export const Methods = {
    GET_SIDEBAR_VISITS  : 'getActiveTabVisitsForSidebar',
    BIND_SIDEBAR_VISITS : 'bindSidebarVisits',
    SEARCH_VISITS_AROUND: 'searchVisitsAround',
    MARK_VISITED        : 'markVisited',
    OPEN_SEARCH         : 'openSearch',
    SIDEBAR_TOGGLE      : 'sidebarToggle',
    // TODO not used
    SIDEBAR_SHOW        : 'sidebarShow',
    ZAPPER_EXCLUDELIST  : 'zapperExcludelist',
}

export const Ids = {
    // visits container in sidebar/search (see sidebar.css)
    VISITS: 'visits',
}

export type SearchPageParams = {
    // TODO allow passing iso string??
    utc_timestamp_s?: string,
    // Query string
    q?: string
}

// $FlowFixMe
export function log(): void {
    const args = [];
    for (var i = 1; i < arguments.length; i++) {
        const arg = arguments[i];
        args.push(JSON.stringify(arg));
    }
    console.trace('[background] ' + arguments[0], ...args);
}


export function asList(bl: string): Array<string> {
    return bl.split(/\n/).filter(s => s.length > 0);
}

export function addStyle(doc: Document, css: string): void {
    const st = doc.createElement('style');
    st.appendChild(doc.createTextNode(css));
    unwrap(doc.head).appendChild(st);
}

export function safeSetInnerHTML(element: HTMLElement, html: string): void {
    const tags = new DOMParser()
          .parseFromString(html, 'text/html')
          .getElementsByTagName('body')[0]
          .childNodes;
    // TODO wtf. if I just use for (t of tags), it doesn't iterate over <br>
    for (const t of Array.from(tags)) {
        element.appendChild(t);
    }
}


// shit. if I type Json properly, then it requires too much isinstance checks...
// https://github.com/facebook/flow/issues/4825

export type JsonArray = Array<Json>
export type JsonObject = $Shape<{ [string]: any }>
export type Json = JsonArray | JsonObject


export function getBrowser(): string {
    // https://stackoverflow.com/questions/12489546/getting-a-browsers-name-client-side
    const agent = window.navigator.userAgent.toLowerCase()
    switch (true) {
        case agent.indexOf("chrome") > -1 && !! window.chrome: return "chrome";
        case agent.indexOf("firefox") > -1                   : return "firefox";
        case agent.indexOf("safari") > -1                    : return "safari";
        case agent.indexOf("edge") > -1                      : return "edge";
        case agent.indexOf("opr") > -1 && !!window.opr       : return "opera";
        case agent.indexOf("trident") > -1                   : return "ie";
        default: return "browser";
    }
}

export function* chunkBy<T>(it: Iterable<T>, count: number): Iterator<Array<T>> {
    let group = []
    for (const i of it) {
        if (group.length == count) {
            yield group
            group = []
        }
        group.push(i)
    }
    if (group.length > 0) {
        yield group
    }
}

export type HttpResponse = {
    headers: any,
    ok: boolean,
    statusText: string,
    text: () => Promise<string>,
}

export function rejectIfHttpError(response: HttpResponse): HttpResponse {
    if (!response.ok) {
        throw Error(response.statusText)
    } else {
        return response
    }
}

// todo ugh, need to use some proper type annotations?
// $FlowFixMe[missing-local-annot]
function fetch_typed(...args): Promise<HttpResponse> {
    // $FlowFixMe
    return fetch(...args)
}

export async function fetch_max_stale(url: string, {max_stale}: {max_stale: number}): Promise<HttpResponse> {
    /* In Firefox, Cache-Control allows max-stale param,
     * which forces the browser to return cached responses past max-age (controlled by server).
     * see https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control#max-stale
     * However, it's not supported for most browsers :(
     * https://github.com/web-platform-tests/wpt/blob/4e0796bcd669c3caf123d5a8f4a2d9acf9e12393/fetch/http-cache/cc-request.any.js#L57
     * https://wpt.fyi/results/fetch/http-cache/cc-request.any.html?label=experimental&label=master&aligned
     * If it was, this function would be as simple as fetch(url, {'Cache-Control': 'max-stale=...'})
     */

    // if it's not cached, it will make a real request
    // anso works offline (returns cached response with no errors)
    const cached_resp = await fetch_typed(url, {cache: 'force-cache'}).then(rejectIfHttpError)
    const expires = cached_resp.headers.get('expires')
    // not sure if it's possible not to have 'expires'
    const stale_ms = new Date() - new Date(expires == null ? 0 : expires)
    const max_stale_ms = max_stale * 1000
    if (stale_ms < max_stale_ms) {
        return cached_resp
    } else {
        // do a regular request instead
        return fetch_typed(url).then(rejectIfHttpError)
    }
}


// useful for debugging
export function uuid(): string {
    return URL.createObjectURL(new Blob([])).substr(-36)
}


export function getOrDefault<T>(obj: any, key: string, def: T): T {
    const res = obj[key];
    return res === undefined ? def : res;
}
