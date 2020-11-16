/* @flow */
import type {Url} from './common';
import {getOptions} from './options'
import {asList} from './common';
import {normalisedURLHostname} from './normalise';

type Reason = string

type UrllistSpec = [string, string]


export class Filterlist {
    filterlist: Array<string>
    urllists: Array<UrllistSpec>

    // cache
    _lists: Map<string, Set<string>>

    constructor({filterlist: filterlist, urllists_json: urllists_json}: {filterlist: string, urllists_json: string}) {
        // FIXME: make it defensive? maybe ignore all on erorrs??
        this.filterlist = asList(filterlist)
        this.urllists   = JSON.parse(urllists_json)

        this._lists = new Map()
    }

    _helper(url: Url): ?Reason {
        // https://github.com/gorhill/uBlock/wiki/How-to-whitelist-a-web-site kind of following this logic and syntax

        // TODO need to be careful about normalising domains here; e.g. cutting off amp/www could be bit unexpected...
        const bl = this.filterlist
        if (bl.includes(url)) {
            return "User-defined filterlist (exact page)"
        }

        const hostname = normalisedURLHostname(url)
        if (bl.includes(hostname)) {
            return "User-defined filterlist (domain)" // TODO maybe supply item number?
        }

        // TODO eh, it's a bit annoying; it tries to handle path segments which we don't really want...
        // const mm = require('micromatch');
        // // console.log(pm.isMatch('http://github.com/issues', ['*github.com/issues*']));
        // if (mm.isMatch(url, bl, {contains: true})) {
        //     return "User-defined filterlist (wildcard)";
        // }

        const regexes = bl.filter(s => s[0] == '/' && s.slice(-1) == '/');
        for (const regex of regexes) {
            if (url.search(RegExp(regex)) >= 0) {
                return `User-defined filterlist (regex: ${regex})`;
            }
        }
        return null
    }

    async _list(name: string, url: string): Promise<Set<string>> {
        let list = this._lists.get(name)
        if (list != null) {
            return list;
        }

        console.debug('loading %s from %s', name, url)

        const {basket} = await import(
            /* webpackChunkName: "basket" */
            // $FlowFixMe
             'basket.js/lib/basket.js'
        )
        // TODO defensive??

        const resp = (await basket.require({
            url    : url,
            execute: false,
            expire : 24 * 3, // 3 days
        }))[0]
        list = new Set(asList(resp.data))
        this._lists.set(name, list);
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
        for (let spec of this.urllists) {
            let bname = spec[0]
            let bfile = spec[1]
            const domains = await this._list(bname, bfile);
            if (domains.has(hostname)) {
                return `'${bname}' filterlist`
            }
        }
        return null;
    }

    static async global(): Promise<Filterlist> {
        const opts = await getOptions()
        return new Filterlist({
            filterlist   : opts.blacklist,
            urllists_json: opts.filterlists,
        })
    }

    static async forMarkVisited(): Promise<Filterlist> {
        return Filterlist.global() // FIXME implement
    }
}
