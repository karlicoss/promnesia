/* @flow */
import {unwrap, asList} from './common';
import type {Url} from './common';

// TODO should probably be merged with common or something...

//
var R = RegExp;

export const
STRIP_RULES = [
    [[R('.*')                     , R('^\\w+://'         )]],
    [[R('.*')                     , R('(www|ww|amp)\\.'  )]],
    [[R('.*')                     , R('[&#].*$'          )]],
    [
        // TODO get rid of these...
        [R('^(youtube|urbandictionary|tesco|scottaaronson|answers.yahoo.com|code.google.com)') , null],
        [R('.*'), R('[\\?].*$')],
    ],
    [[R('.*')                     , R('/$'               )]],
]
; // TODO perhaps that should be semi-configurable

// TODO maybe use that normalisation library and then adjust query params etc

/*
  I think, most common usecases are:
  - blacklisting whole domain (e.g. for privacy reasons, like bank/etc or if something is broken)
  - blacklisting specific pages (e.g. reddit/twitter/fb main page so it doesn't result it too many child contexts)
  For that current approach is fine.
*/

// TODO careful about dots etc?

export function normalise_url(url: string): string {
    let cur = url;
    STRIP_RULES.forEach((rules: Array<Array<?RegExp>>) => { // meh impure foreach..
        for (const rule of rules) {
            const target: RegExp = unwrap(rule[0]);
            const reg: ?RegExp = rule[1];
            if (cur.search(target) >= 0) {
                console.log("[normalise] %s: matched %s, applying %s", cur, target, reg);
                if (reg != null) {
                    cur = cur.replace(reg, '');
                }
                break;
            }
        }
    });
    return cur;
}

const _re = R('^(www|ww|amp)\\.'  );
export function normaliseHostname(url: string): string {
    return url.replace(_re, '');
}


export function normalisedURLHostname(url: Url): string {
    const _hostname = new URL(url).hostname;
    const hostname = normaliseHostname(_hostname);
    return hostname;
}


export function isBlacklistedHelper(url: Url, blacklist: string): ?string {
    // https://github.com/gorhill/uBlock/wiki/How-to-whitelist-a-web-site kind of following this logic and syntax

    // TODO need to be careful about normalising domains here; e.g. cutting off amp/www could be bit unexpected...
    const bl = asList(blacklist);
    if (bl.includes(url)) {
        return "User-defined blacklist (exact page)";
    }

    const hostname = normalisedURLHostname(url);
    if (bl.includes(hostname)) {
        return "User-defined blacklist (domain)"; // TODO maybe supply item number?
    }

    // TODO eh, it's a bit annoying; it tries to handle path segments which we don't really want...
    // const mm = require('micromatch');
    // // console.log(pm.isMatch('http://github.com/issues', ['*github.com/issues*']));
    // if (mm.isMatch(url, bl, {contains: true})) {
    //     return "User-defined blacklist (wildcard)";
    // }

    const regexes = bl.filter(s => s[0] == '/');
    console.log(regexes);
    for (const regex of regexes) {
        if (url.search(RegExp(regex)) >= 0) {
            return `User-defined blacklist (regex: ${regex})`;
        }
    }

    return null;
}
