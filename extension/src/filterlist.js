/* @flow */
import type {Url} from './common';
import {getOptions} from './options'
import {asList, fetch_max_stale} from './common'
import {normalisedURLHostname} from './normalise';

type Reason = string

type UrllistSpec = [string, string]


export class Filterlist {
    filterlist: Set<string>
    // TODO rename to 'external lists or something'
    urllists: Array<UrllistSpec>

    // cache
    _lists: Map<string, Set<string>>

    constructor({filterlist: filterlist, urllists_json: urllists_json}: {filterlist: string, urllists_json: string}) {
        // FIXME: make it defensive? maybe ignore all on erorrs??
        this.filterlist = new Set(asList(filterlist))
        this.urllists   = JSON.parse(urllists_json)

        this._lists = new Map()
    }

    // TODO use some extra cache?
    _helper(url: Url): ?Reason {
        // https://github.com/gorhill/uBlock/wiki/How-to-whitelist-a-web-site kind of following this logic and syntax

        const noslash = url.replace(/\/+$/, '') // meh
        // TODO need to be careful about normalising domains here; e.g. cutting off amp/www could be bit unexpected...
        // TODO maybe use URL class instead?
        if (   this.filterlist.has(url)
            || this.filterlist.has(noslash)
            || this.filterlist.has(url + '/')
           ) {
            return "User-defined filterlist (exact page)"
        }

        const hostname = normalisedURLHostname(url)
        if (this.filterlist.has(hostname)) {
            return `User-defined filterlist (domain ${hostname})` // TODO maybe supply item number?
        }

        // TODO eh, it's a bit annoying; it tries to handle path segments which we don't really want...
        // const mm = require('micromatch');
        // // console.log(pm.isMatch('http://github.com/issues', ['*github.com/issues*']));
        // if (mm.isMatch(url, bl, {contains: true})) {
        //     return "User-defined filterlist (wildcard)";
        // }

        for (const f of this.filterlist) {
            const is_regex = f[0] == '/' && f.slice(-1) == '/'
            if (is_regex && url.search(RegExp(f)) >= 0) {
                return `User-defined filterlist (regex: ${f})`;
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

        // clear old basket.js local storge
        for (const key of Object.keys(localStorage)) {
            if (key.startsWith('basket-')) {
                localStorage.removeItem(key)
            }
        }

        if (url.includes('/cbuijs/shallalist/')) {
            // use my fork just in case... they stopped updating the list anyway
            url = url.replace('/cbuijs/shallalist/', '/karlicoss/shallalist/')
            // the cbuijs repo switched to main branch, so let's do that too
            url = url.replace('/master/', '/main/')
            // see https://github.com/karlicoss/promnesia/issues/325
            console.debug('replacing shallalist entry to %s', url)
        }

        // ugh. so for github (where the shallalist lists are kept), server max-age is about 5 mins
        // so relying on default caching will result in downloading lists every 5 minutes
        const max_stale = 24 * 3600  // 1 day
        let contents = null
        try {
            const response = await fetch_max_stale(url, {max_stale: max_stale})
            contents = await response.text()
        } catch (error) {
            console.error('suppressing error until we have a proper fix: %o', error)
            contents  = '[]'
            // TODO not sure how to fix this properly..
            // I guess it should cache things and only update when the request succeeds
            // but also what if it fails on the first request??
            // probably should be defensive list by list, but also report error to the UI
            // and suggest suppressing list in settings for example
        }
        // so I guess it's abit suboptimal to query every 5 minutes... idk
        list = new Set(asList(contents))
        this._lists.set(name, list);
        return list;
    }

    async contains(url: Url): Promise<?Reason> {
        try {
            new URL(url);
        } catch {
            return "invalid URL"
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
            urllists_json: opts.global_excludelists_ext,
        })
    }

    static async forMarkVisited(): Promise<Filterlist> {
        const opts = await getOptions()
        // merges together both global and the one for mark visited
        return new Filterlist({
            filterlist   : opts.blacklist + '\n' + opts.mark_visited_excludelist,
            urllists_json: opts.global_excludelists_ext,
        })
    }
}
