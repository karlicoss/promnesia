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
        throw "undefined or null!";
    }
    return x;
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
}

type VisitsList = Array<Visit>;

export class Visits {
    original_url: Url;
    normalised_url: Url;
    visits: VisitsList;

    constructor(original_url: Url, normalised_url: Url, visits: VisitsList) {
        this.original_url = original_url;
        this.normalised_url = normalised_url;
        this.visits = visits;
    }

    self_contexts(): Array<?Locator> {
        const locs = [];
        for (const visit of this.visits) {
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
        for (const visit of this.visits) {
            if (visit.context === null) {
                continue;
            }
            if (visit.normalised_url != this.normalised_url) {
                locs.push(visit.locator);
            }
        }
        return locs;
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
};


// $FlowFixMe
export function log() {
    const args = [];
    for (var i = 1; i < arguments.length; i++) {
        const arg = arguments[i];
        args.push(JSON.stringify(arg));
    }
    console.trace('[background] ' + arguments[0], ...args);
}

export const ldebug = log; // TODO
export const lwarn = log; // TODO
export const linfo = log; // TODO
export const lerror = log; // TODO


export function asList(bl: string): Array<string> {
    return bl.split(/\n/).filter(s => s.length > 0);
}

export function addStyle(doc: Document, css: string) {
    const st = doc.createElement('style');
    st.appendChild(doc.createTextNode(css));
    unwrap(doc.head).appendChild(st);
}

export function safeSetInnerHTML(element: HTMLElement, html: string) {
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
