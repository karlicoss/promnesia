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
            // $FlowFixMe
            const ondone = (r: R) => {
                const err = chrome.runtime.lastError
                if (err) {
                    reject(err)
                } else { // TODO I didn't have else at first??
                    resolve(r)
                }
            }
            fn(...args, ondone)
        })
    }
}

// fucking hell.. also had to make them properties because apis might not exist in certain contexts
// e.g. access to chrome.tabs.get might crash
export const achrome = {
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
}


// TODO legacy, remove
export function chromeTabsExecuteScriptAsync(tabId: number, opts: any): Promise<?Array<any>> {
    return achrome.tabs.executeScript(tabId, opts)
}
export function chromeTabsInsertCSS(tabId: number, opts: any): Promise<void> {
    return achrome.tabs.insertCSS(tabId, opts)
}
