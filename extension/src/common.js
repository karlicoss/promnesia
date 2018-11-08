/* @flow */

export type Url = string;
export type Tag = string;
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


    constructor(time: string, tags: Array<Tag>) {
        this.time = time;
        this.tags = tags;
    }

    repr(): string {
        return this.time  + " " + this.tags.toString();
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
