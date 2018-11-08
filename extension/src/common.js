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
    // TODO parse it
}

export class Visits {
    visits: Array<any>;
    contexts: Array<any>;

    constructor(visits: Array<any>, contexts: Array<any>) {
        this.visits = visits;
        this.contexts = contexts;
    }
}
