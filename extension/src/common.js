/* @flow */

export type Url = string;
export type Tag = string;
export type Locator = string;
export type VisitsMap = {[Url]: Visits};
export type Dt = Date;

export function unwrap<T>(x: ?T): T {
    if (!x) {
        throw "undefined or null!";
    }
    return x;
}


export function date_formatter() {
    const options = {
        day   : 'numeric',
        month : 'short',
        year  : 'numeric',
        hour  : 'numeric',
        minute: 'numeric',
    };
    return new Intl.DateTimeFormat('en-GB', options);
}

// UGH there are no decent custom time format functions in JS..
export function format_dt(dt: Date): string {
    const dts = date_formatter().format(dt);
    return dts.replace(',', '');
}

export class Visit {
    time: Dt;
    tags: Array<Tag>;
    context: ?string;
    locator: ?string;


    constructor(time: Dt, tags: Array<Tag>, context: ?string=null, locator: ?string=null) {
        this.time = time;
        this.tags = tags;
        this.context = context;
        this.locator = locator;
    }

    repr(): string {
        return format_dt(this.time)  + " " + this.tags.toString();
    }
}

type VisitsList = Array<Visit>;

export class Visits {
    visits: VisitsList;

    constructor(visits: VisitsList) {
        this.visits = visits;
    }

    contexts(): Array<?Locator> {
        const locs = [];
        for (const visit of this.visits) {
            if (visit.context === null) {
                continue;
            }
            locs.push(visit.locator);
        }
        return locs;
    }
}
