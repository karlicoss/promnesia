/* @flow */

export type Url = string;
export type Tag = string;
export type Locator = string;
export type VisitsMap = {[Url]: Visits};

export function unwrap<T>(x: ?T): T {
    if (!x) {
        throw "undefined or null!";
    }
    return x;
}


export class Visit {
    time: string;
    tags: Array<Tag>;
    context: ?string;
    locator: ?string;


    constructor(time: string, tags: Array<Tag>, context: ?string=null, locator: ?string=null) {
        this.time = time;
        this.tags = tags;
        this.context = context;
        this.locator = locator;
    }

    repr(): string {
        return this.time  + " " + this.tags.toString();
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
