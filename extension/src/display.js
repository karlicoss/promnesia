/* @flow */
import type {Url, Src, Locator} from './common';
import {Methods, unwrap, safeSetInnerHTML} from './common';
import type {Options} from './options'

export function _fmt(dt: Date): [string, string] {
    // todo if it's this year, do not display year?
    // meh. it really does seem like the easiest way to enforce a consistent date
    // Intl is crap and doesn't allow proper strftime-like formatting
    // maybe it should be a user setting later, dunno
    const dts = dt.toString()
    const parts = dts.split(' ')
    // smth like Tue Nov 03 2020 01:53:46 GMT+0000
    var [mon, day, year] = parts.slice(1, 4)
    day = day[0] == '0' ? day[1] : day
    // eslint-disable-next-line no-unused-vars
    var [hh , mm , ss] = parts[4].split(':')

    const datestr = `${day} ${mon} ${year}`
    const timestr = `${hh}:${mm}`
    return [datestr, timestr]
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

// todo use opaque type? makes it annoying to convert literal strings...
type CssClass = string
export function asClass(x: string): CssClass {
    // todo meh. too much trouble to fix properly...
    const res = x.replace(/\s/g, '');
    return res.length == 0 ? 'bad_class' : res
}


export class Binder {
    doc: Document
    options: Options

    constructor(doc: Document, options: Options) {
        this.doc = doc
        this.options = options
    }

    makeChild(parent: HTMLElement, name: string, classes: ?Array<CssClass> = null): HTMLElement {
        const res = this.doc.createElement(name);
        if (classes != null) {
            for (const cls of classes) {
                res.classList.add(cls);
            }
        }
        parent.appendChild(res);
        return res;
    }

    makeTchild(parent: HTMLElement, text: string): Text {
        const res = this.doc.createTextNode(text);
        parent.appendChild(res);
        return res;
    }

    async renderError(
        parent: HTMLElement,
        error: Error,
    ): Promise<void> {
        // $FlowFixMe[method-unbinding]
        const child  = this.makeChild .bind(this)
        // $FlowFixMe[method-unbinding]
        const tchild = this.makeTchild.bind(this)

        const item = child(parent, 'li', ['error'])
        const ec   = child(item  , 'code')
        // todo not sure if need any other info?
        tchild(ec, `${error.name}: ${error.message}\n${error.stack}`)
    }

    async render(
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
    ): Promise<HTMLElement> {
        // todo ugh. looks like Flow can't guess the type of closure that we get by .bind...
        // $FlowFixMe[method-unbinding]
        const child = this.makeChild.bind(this);
        // $FlowFixMe[method-unbinding]
        const tchild = this.makeTchild.bind(this); // TODO still necessary??

        const item = child(parent, 'li', relative ? ['relative'] : []);
        const header = child(item, 'div');
        const relative_c = child(header, 'span');
        relative_c.id = 'relative_indicator';
        const tags_c = child(header, 'span');

        const dt_c = child(header, 'span', ['datetime']);
        const time_c = child(dt_c, 'span', ['time']);
        const date_c = child(dt_c, 'span', ['date']);
        item.setAttribute('data-sources', asClass(tags.join(' ')));

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
            const tag_c = child(tags_c, 'span', ['src', asClass(tag)]);
            tchild(tag_c, asClass(tag));
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


        if (context != null) {
            const ctx_c = child(item, 'div', ['context'])

            // ugh.. so much code foe something so simple
            function do_simple(text: string) {
                for (const line of text.split('\n')) {
                    tchild(ctx_c, line)
                    child (ctx_c, 'br')
                }
            }
            let handle_plain = do_simple

            if (this.options.sidebar_detect_urls) {
                // ugh. this method triggers this issue during web-ext lint
                // presumably because web-ext doesn't like querying chrome.runtime.getURL
                // reported here https://github.com/mozilla/addons-linter/issues/4686
                // NOTE: import might fail on some pages, e.g. twitter.com. so needs to be defensive
                // upd: actually not sure if import on twitter page is really an issue anymore? seems to work...
                // try {
                //     // NOTE: anchorme.js needs to be in web_accessible_resources for this to work
                //     // $FlowFixMe[unsupported-syntax]
                //     await import (/* webpackIgnore: true */ chrome.runtime.getURL('anchorme.js'))
                //     // this sets window.promnesia_anchorme -- see webpack.config.js
                // } catch (err) {
                //     console.error(err)
                //     console.warn("[promnesia] couldn't import anchorme. Fallback on plaintext")
                // }
                // note: performance is OK
                // 339 iterations passed, took  200  ms -- and it's counting other DOM operations as well
                if (window.promnesia_anchorme != null) {
                    const anchorme = window.promnesia_anchorme.default
                    handle_plain = (text: string) => {
                        try {
                            const res = unwrap(anchorme)(text)
                            safeSetInnerHTML(ctx_c, res)
                        } catch (err) { // just in case..
                            console.error(err)
                            do_simple(text)
                        }
                    }
                }
            }

            let ctx = context;
            if (ctx.startsWith(HTML_MARKER)) {
                ctx = context.substring(HTML_MARKER.length)
                safeSetInnerHTML(ctx_c, ctx);
            } else { // plaintext
                handle_plain(ctx)
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

                // _self seems to "work" only for the "editor://" protocol. Avoids opening a new tab for "editor://" links. Nttp links then require a middle-click, which is undesirable. With normal click, they would not open at all.
                // testing on firefox mobile would be useful.
                // note that on some pages, like https://news.ycombinator.com/, this (clicking on a _self editor:// link) results in: Content Security Policy: The page’s settings blocked the loading of a resource at editor:///home/koom/promnesia/docker//user_data/source1/notes/g1:12 (“frame-src”).
                // but middle-click still works.
                // on others (https://www.reddit.com/), it just works.
                // so, if we should do this at all is a question.
                //if (link.href.startsWith('editor://'))
                //    link.target= '_self';

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

