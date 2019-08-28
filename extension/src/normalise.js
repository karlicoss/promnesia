/* @flow */
import {unwrap} from './common';
import type {Url} from './common';

//
var R = RegExp;

export const
STRIP_RULES = [
    [[R('.*')                     , R('^\\w+://'         )]],
    [[R('.*')                     , R('(www|ww|amp)\\.'  )]],
    [[R('.*')                     , R('[&#].*$'          )]],
    [
        [R('^(youtube|urbandictionary|tesco|scottaaronson|answers.yahoo.com|code.google.com)') , null],
        [R('.*'), R('[\\?].*$')],
    ],
    [[R('.*')                     , R('/$'               )]],
]
; // TODO perhaps that should be semi-configurable

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
