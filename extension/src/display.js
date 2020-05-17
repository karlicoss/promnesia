/* @flow */
import type {Url, Src, Locator} from './common';
import {format_dt, Methods, unwrap, safeSetInnerHTML} from './common';

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
    idx: ?number;
    timestamp: Date;
    original_url: ?Url;
    normalised_url: ?Url;
    context: ?string;
    locator: ?Locator;
    relative: boolean;
}


const HTML_MARKER = '!html ';

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

    error(
        parent: HTMLElement,
        message: string,
    ) {
        const child = this.makeChild.bind(this);
        const tchild = this.makeTchild.bind(this); // TODO still necessary??

        const item = child(parent, 'div', ['error']);
        tchild(item, "ERROR: " + message);
    }

    render(
        parent: HTMLElement,
        dates: string,
        times: string,
        tags: Array<Src>,
        {
            idx,
            timestamp,
            original_url,
            normalised_url,
            context,
            locator,
            relative,
        }: Params,
    ) {
        const child = this.makeChild.bind(this);
        const tchild = this.makeTchild.bind(this); // TODO still necessary??

        const item = child(parent, 'li', relative ? ['relative'] : []);
        const header = child(item, 'div');
        const relative_c = child(header, 'span');
        relative_c.id = 'relative_indicator';
        const tags_c = child(header, 'span');

        const dt_c = child(header, 'span', ['datetime']);
        const time_c = child(dt_c, 'span', ['time']);
        const date_c = child(dt_c, 'span', ['date']);
        item.setAttribute('sources', tags.join(' '));

        const child_link = child(relative_c, 'a');
        // ugh. not sure why opening in new tab doesn't work :(
        // https://stackoverflow.com/questions/12454382/target-blank-is-not-working-in-firefox/12454474#12454474
        // child_link.target = '_blank';
        child_link.href = original_url;
        tchild(child_link, '➤➤');

        const idx_c = child(tags_c, 'span', ['index']);
        idx_c.title = 'index (for easier match against highlights)';
        if (idx != null) {
            tchild(idx_c, String(idx));
        }
        for (const tag of tags) {
            const tag_c = child(tags_c, 'span', ['src', tag]);
            tchild(tag_c, tag);
        }
        tchild(date_c, dates);

        // TODO style it properly?
        tchild(time_c, times);
        dt_c.setAttribute('title', 'search around');
        dt_c.onclick = () => {
            // TODO not sure about floor...
            const utc_timestamp_s = Math.floor(timestamp.getTime() / 1000);
            chrome.runtime.sendMessage({
                method   : Methods.SEARCH_VISITS_AROUND,
                utc_timestamp_s: utc_timestamp_s,
            });

            return true;
        };

        /* TODO locator could jump into the file? */
        if (context != null) {
            const ctx_c = child(item, 'div', ['context'])

            let ctx = context;
            if (ctx.startsWith(HTML_MARKER)) {
                ctx = context.substring(HTML_MARKER.length)
                safeSetInnerHTML(ctx_c, ctx);
            } else { // plaintext
                for (const line of ctx.split('\n')) {
                    tchild(ctx_c, line)
                    child(ctx_c, 'br')
                }
            }
        }

        if (locator != null) {
            const loc = locator;
            const loc_c = child(item, 'div', ['locator']);

            if (loc.href === null) {
                tchild(loc_c, loc.title);
            } else {
                const link = child(loc_c, 'a');
                link.title = 'Jump to the context';
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

        // right, this is for search..
        if (normalised_url != null) {
            const nurl_c = child(item, 'div', ['normalised_url']);
            const link = child(nurl_c, 'a');
            link.href = unwrap(original_url);
            tchild(link, normalised_url);
        }

        return item;
    }
}

