/* @flow */

// sigh.. callback as the last argument is pretty annoying..
// don't think it can be typed properly? i.e. we can't write ...args, cb: (R => void)
// also even ...args: $ReadOnlyArray<any | (R => void)> doesn't work ;( 

// ugh. also couldn't force it to accept the substructure..
type Arg = any


// ugh fuck. also there is no partial application for types, so classes are a way around?
class Awrap0 {
    wrap<R>(fn: ((
        cb: (R => void)) => void))
    : (()         => Promise<R>)
    {
        // $FlowFixMe
        return helper(fn)
    }
}

class Awrap1<A> {
    wrap<R>(fn: ((
        arg1: Arg,
        cb: (R => void)) => void))
    : ((arg1: A) => Promise<R>)
    {
        // $FlowFixMe
        return helper(fn)
    }
}

class Awrap2<A1, A2> {
    wrap<R>(fn: ((
        arg1: Arg,
        arg2: Arg,
        cb: (R => void)) => void))
    : ((arg1: A1, arg2: A2) => Promise<R>)
    {
        // $FlowFixMe
        return helper(fn)
    }
}


// $FlowFixMe
function helper<R, TArgs: *>(fn): ((...args: TArgs) => Promise<R>) {
    return (...args: Array<any>) => {
        return new Promise((resolve, reject) => {
            const ondone = (r: R) => {
                const err = chrome.runtime.lastError
                if (err) {
                    reject(err)
                } else { // TODO I didn't have else at first??
                    resolve(r)
                }
            }
            // $FlowFixMe
            fn(...args, ondone)
        })
    }
}

// fucking hell.. also had to make them properties because apis might not exist in certain contexts
// e.g. access to chrome.tabs.get might crash
export const achrome = {
    // $FlowFixMe
    bookmarks: {
        // $FlowFixMe
        get search       () { return new Awrap1<{url: string}                              >().wrap(chrome.bookmarks.search  ) },
        // $FlowFixMe
        get getTree      () { return new Awrap0                                             ().wrap(chrome.bookmarks.getTree ) },
    },
    // $FlowFixMe
    tabs: {
        // $FlowFixMe
        get get          () { return new Awrap1<number                                     >().wrap(chrome.tabs.get          ) },
        // $FlowFixMe
        get query        () { return new Awrap1<{currentWindow?: boolean, active?: boolean}>().wrap(chrome.tabs.query        ) },
        // $FlowFixMe
        get executeScript() { return new Awrap2<number, {file?: string, code?: string}     >().wrap(chrome.tabs.executeScript) },
        // $FlowFixMe
        get insertCSS    () { return new Awrap2<number, {file?: string, code?: string}     >().wrap(chrome.tabs.insertCSS    ) },
    },
    // $FlowFixMe
    runtime: {
        // $FlowFixMe
        get getPlatformInfo() { return new Awrap0    ().wrap(chrome.runtime.getPlatformInfo) },
        // $FlowFixMe
        get sendMessage    () { return new Awrap1<{}>().wrap(chrome.runtime.sendMessage    ) },
    },
    // $FlowFixMe
    history: {
        // crap, missing in flow-interfaces-chrome
        // $FlowFixMe
        get getVisits    () { return new Awrap1<{url: string }>().wrap<Array<VisitItem>>(
            // $FlowFixMe
            chrome.history.getVisits
        ) },
        // $FlowFixMe
        get search       () { return new Awrap1<{text: string, startTime?: number, endTime?: number}>().wrap<Array<HistoryItem>>(
            // $FlowFixMe
            chrome.history.search
        )}
    },
}

// https://developer.chrome.com/extensions/history#type-HistoryItem
type VisitItem = {
    visitTime?: number,
}

export type HistoryItem = {
    url?: string,
    lastVisitTime?: number,
}

