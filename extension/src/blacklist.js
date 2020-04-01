/* @flow */
import type {Url} from './common';
import {asList} from './common';
import {normalisedURLHostname} from './normalise';

type Reason = string;


export class Blacklist {
    // TODO use Set?
    blacklist: Array<string>;

    constructor(blacklist_string: string) {
        this.blacklist = asList(blacklist_string);
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

    async contains(url: Url): Promise<?Reason> {
        // for now assumes it's exact domain match domain level
        const user_blacklisted = this._helper(url);
        // TODO test shallalist etc as well?
        if (user_blacklisted !== null) {
            return user_blacklisted;
        }

        const hostname = normalisedURLHostname(url);
        // TODO perhaps use binary search?
        // TODO not very efficient... I guess I need to refresh it straight from github now and then?
        // TODO keep cache in local storage or something?
        for (let [bname, bfile] of [
            ['Webmail', 'shallalist/webmail/domains'],
            ['Banking', 'shallalist/finance/banking/domains'],
        ]) {
            const domains_url = chrome.runtime.getURL(bfile);
            // TODO do we really need await here??
            const resp = await fetch(domains_url);
            const domains = asList(await resp.text());
            if (domains.includes(hostname)) {
                return `'${bname}' blacklist`;
            }
        }
        return null;
    }
}
