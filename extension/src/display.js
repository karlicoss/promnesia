/* @flow */
import type {Url, Tag, Locator} from './common';
import {format_dt, Methods, unwrap} from './common';

// TODO need to pass document??


export function _fmt(dt: Date): [string, string] {
    // TODO if it's this year, do not display year?
    const dts = format_dt(dt);
    const parts = dts.split(' ');
    const datestr = parts.slice(0, 3).join(' ');
    const timestr = parts.slice(3).join(' ');
    return [datestr, timestr];
}

type Params = {
    original_url: ?Url;
    normalised_url: ?Url;
    context: ?string;
    locator: ?Locator;
}

export class Binder {
    doc: Document;

    constructor(doc: Document) {
        this.doc = doc;
    }

    makeChild(parent: HTMLElement, name: string, classes: ?Array<string> = null) {
        const res = this.doc.createElement(name);
        if (classes != null) {
            for (const cls of classes) {
                res.classList.add(cls);
            }
        }
        parent.appendChild(res);
        return res;
    }

    makeTchild(parent: HTMLElement, text: string) {
        const res = this.doc.createTextNode(text);
        parent.appendChild(res);
        return res;
    }

    render(
        parent: HTMLElement,
        dates: string,
        times: string,
        tags: Array<Tag>,
        {
            original_url,
            normalised_url,
            context,
            locator,
        }: Params,
    ) {
        const child = this.makeChild.bind(this);
        const tchild = this.makeTchild.bind(this); // TODO still necessary??


        const item = child(parent, 'li');
        const header = child(item, 'div');
        const tags_c = child(header, 'span');
        const dt_c = child(header, 'span', ['datetime']);
        const time_c = child(dt_c, 'span', ['time']);
        const date_c = child(dt_c, 'span', ['date']);

        item.setAttribute('tags', tags.join(" "));

        for (const tag of tags) {
            const tag_c = child(tags_c, 'span', ['tag', tag]);
            tchild(tag_c, tag);
        }
        tchild(date_c, dates);

        // TODO style it properly?
        tchild(time_c, times);
        time_c.onclick = function() {
            const timestamp = 1564604609; // TODO FIXME
            chrome.runtime.sendMessage({
                method   : Methods.SEARCH_VISITS_AROUND,
                timestamp: timestamp,
            });

            return true;
        };

        /* TODO locator could jump into the file? */
        if (context != null) {
            const ctx_c = child(item, 'div', ['context']);
            for (const line of context.split('\n')) {
                tchild(ctx_c, line);
                child(ctx_c, 'br');
            }
        }

        if (locator != null) {
            const loc = locator;
            const loc_c = child(item, 'div', ['locator']);

            if (loc.href === null) {
                tchild(loc_c, loc.title);
            } else {
                const link = child(loc_c, 'a');
                // $FlowFixMe
                link.href = loc.href;
                tchild(link, loc.title);
            }

            /*
            const trim_till = Math.min(context.indexOf('\n'), 100);
            const firstline = context.substring(0, trim_till);

            // TODO do not throw this away?
            const firstline_elem = doc.createTextNode(firstline);

            const det = doc.createElement('details'); ccell.appendChild(det);
            const summ = doc.createElement('summary'); det.appendChild(summ);

            summ.appendChild(loc_elem);
            // TODO not sure if we want to do anything if we have trimmed locator...
            // TODO at least add some space?
            summ.appendChild(firstline_elem);
            det.appendChild(doc.createTextNode(context));
            */
        }
        if (normalised_url != null) {
            const nurl_c = child(item, 'div', ['normalised_url']);
            const link = child(nurl_c, 'a');
            link.href = unwrap(original_url);
            tchild(link, normalised_url);
        }
    }
}

