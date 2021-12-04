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
        return helper(fn)
    }
}

class Awrap1<A> {
    wrap<R>(fn: ((
        arg1: Arg,
        cb: (R => void)) => void))
    : ((arg1: A) => Promise<R>)
    {
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
        return helper(fn)
    }
}


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
    bookmarks: {
        get search       () { return new Awrap1<{url: string}                              >().wrap(chrome.bookmarks.search  ) },
        get getTree      () { return new Awrap0                                             ().wrap(chrome.bookmarks.getTree ) },
    },
    tabs: {
        get get          () { return new Awrap1<number                                     >().wrap(chrome.tabs.get          ) },
        get query        () { return new Awrap1<{currentWindow?: boolean, active?: boolean}>().wrap(chrome.tabs.query        ) },
        get executeScript() { return new Awrap2<number, {file?: string, code?: string}     >().wrap(chrome.tabs.executeScript) },
        get insertCSS    () { return new Awrap2<number, {file?: string, code?: string}     >().wrap(chrome.tabs.insertCSS    ) },
    },
    runtime: {
        get getPlatformInfo() { return new Awrap0    ().wrap(chrome.runtime.getPlatformInfo) },
        get sendMessage    () { return new Awrap1<{}>().wrap(chrome.runtime.sendMessage    ) },
    },
    history: {
        // crap, missing in flow-interfaces-chrome
        get getVisits    () { return new Awrap1<{url: string }>().wrap<Array<VisitItem>>(
            // $FlowFixMe
            chrome.history.getVisits
        ) },
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

