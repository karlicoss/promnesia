/* @flow */
import type {Url} from './common';
import {asList, log} from './common';
import {normalisedURLHostname} from './normalise';

type Reason = string;


export class Blacklist {
    // TODO use Set?
    blacklist: Array<string>;
    lists: Map<string, Set<string>>;

    constructor(blacklist_string: string) {
        this.blacklist = asList(blacklist_string);
        this.lists = new Map();
    }

    _helper(url: Url): ?string {
        // https://github.com/gorhill/uBlock/wiki/How-to-whitelist-a-web-site kind of following this logic and syntax

        // TODO need to be careful about normalising domains here; e.g. cutting off amp/www could be bit unexpected...
        const bl = this.blacklist;
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

        const regexes = bl.filter(s => s[0] == '/' && s.slice(-1) == '/');
        for (const regex of regexes) {
            if (url.search(RegExp(regex)) >= 0) {
                return `User-defined blacklist (regex: ${regex})`;
            }
        }

        return null;
    }

    async _list(name: string, url: string): Promise<Set<string>> {
        let list = this.lists.get(name);
        if (list != null) {
            return list;
        }

        log('loading %s from %s', name, url)

        const {basket} = await import(
            /* webpackChunkName: "basket" */
            // $FlowFixMe
             'basket.js/lib/basket.js'
        )
        // FIXME defensive??

        const resp = (await basket.require({
            url    : url,
            execute: false,
            expire : 24 * 3, // 3 days
        }))[0]
        list = new Set(asList(resp.data))
        this.lists.set(name, list);
        return list;
    }

    async contains(url: Url): Promise<?Reason> {
        try {
            new URL(url);
        } catch {
            // TODO test this?
            return "invalid URL";
        }

        // for now assumes it's exact domain match domain level
        const user_blacklisted = this._helper(url);
        if (user_blacklisted !== null) {
            return user_blacklisted;
        }

        const hostname = normalisedURLHostname(url);
        // TODO perhaps use binary search?
        for (let [bname, bfile] of [
            // TODO use a proper CDN?
            ['Webmail', 'https://raw.githubusercontent.com/cbuijs/shallalist/master/webmail/domains'        ],
            ['Banking', 'https://raw.githubusercontent.com/cbuijs/shallalist/master/finance/banking/domains'],
        ]) {
            const domains = await this._list(bname, bfile);
            if (domains.has(hostname)) {
                return `'${bname}' blacklist`;
            }
        }
        return null;
    }
}
