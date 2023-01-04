/* @flow */
import {unwrap} from './common';
import type {Url} from './common';

// TODO should probably be merged with common or something...

//
var R = RegExp;

const
STRIP_RULES = [
    [[R('.*')                     , R('^\\w+://'         )]],
    [[R('.*')                     , R('(www|ww|amp)\\.'  )]],
    [[R('.*')                     , R('[&#].*$'          )]],
    [[R('.*')                     , R('/$'               )]],
]
// TODO perhaps that should be semi-configurable

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
