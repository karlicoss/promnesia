/* @flow */

export type Url = string;
export type VisitsMap = {[Url]: Visits};

export function unwrap<T>(x: ?T): T {
    if (!x) {
        throw "undefined or null!";
    }
    return x;
}


export class Visit {
    vs: string;

    constructor(vs: string) {
        this.vs = vs;
        // TODO parse it or use static mehtod
    }

    repr(): string {
        return this.vs;
    }
}

type VisitsList = Array<Visit>;

export class Visits {
    visits: VisitsList;
    contexts: Array<any>;

    constructor(visits: VisitsList, contexts: Array<any>) {
        this.visits = visits;
        this.contexts = contexts;
    }
}
