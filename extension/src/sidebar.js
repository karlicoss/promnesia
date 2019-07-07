/* @flow */
import {Visits, Visit, unwrap, format_dt} from './common';
import type {Tag, Locator} from './common';
import {get_options} from './options';
import type {Options} from './options';

import React from 'react';
import ReactDOM from 'react-dom';
// $FlowFixMe
import { Frame } from 'chrome-sidebar';

// TODO how to prevent sidebar hiding on click??

const SIDEBAR_ID = "wereyouhere-sidebar";

function toggleSidebar() {
    if (Frame.isReady()) {
        Frame.toggle();
    } else {
        boot();
    }
}
// to make function available for executeScript... gross
window.toggleSidebar = toggleSidebar;


function getSidebarNode(opts: Options): ?HTMLElement {
    const extra_css = opts.extra_css;

    const root = document.getElementById(SIDEBAR_ID);
    // $FlowFixMe
    if (root == null) {
        return null;
    }
    const frame = root.getElementsByTagName('iframe')[0];
    // TODO this should be configured..
    frame.style.background = "rgba(236, 236, 236, 0.4)";

    const cdoc = frame.contentDocument;
    const link = cdoc.createElement("link");
    link.href = chrome.extension.getURL("sidebar.css");
    link.type = "text/css";
    link.rel = "stylesheet";
    const head  = cdoc.getElementsByTagName("head")[0]; // TODO why [0]??
    head.appendChild(link);

    const style = cdoc.createElement('style');
    style.innerHTML = extra_css;
    head.appendChild(style);

    // make links open in new tab instead of iframe https://stackoverflow.com/a/2656798/706389
    const base = cdoc.createElement('base');
    base.setAttribute('target', '_blank');
    head.appendChild(base);


    const cont = root.children[0].children[1]; // TODO very fragile... div data-reactroot -> some other thing that is an actual container
    cont.style.cssText = "max-width: 500px !important;"; // override CSS enforced 400px thing https://github.com/segmentio/chrome-sidebar/blob/ae9f07e97bb08927631d1f2eb5fb31e965959bde/src/frame.js#L36

    return cdoc.body;
    // right, iframe is pretty convenient for scrolling...

    // return (cont: HTMLElement);
}

function get_or_default(obj, key, def) {
    const res = obj[key];
    return res === undefined ? def : res;
}

// This is pretty insane... but it's the only sidebar lib I found :(
function clearSidebar(opts: Options) {
    const cont = unwrap(getSidebarNode(opts));
    while (cont.firstChild) {
        cont.removeChild(cont.firstChild);
    }
}

function _fmt(dt: Date): [string, string] {
    // TODO if it's this year, do not display year?
    const dts = format_dt(dt);
    const parts = dts.split(' ');
    const datestr = parts.slice(0, 3).join(' ');
    const timestr = parts.slice(3).join(' ');
    return [datestr, timestr];
}

function bindSidebarData(response) {
    get_options(opts => bindSidebarDataAux(response, opts));
}

function bindSidebarDataAux(response, opts: Options) {
    const cont = getSidebarNode(opts);
    if (cont == null) {
        console.log('no sidebar, so not binding anything');
        return;
    }
    clearSidebar(opts);
    console.log(response);

    const doc = document;

    function child(parent, name: string, classes: ?Array<string> = null) {
        const res = doc.createElement(name);
        if (classes != null) {
            for (const cls of classes) {
                res.classList.add(cls);
            }
        }
        parent.appendChild(res);
        return res;
    }

    function tchild(parent, text: string) {
        const res = doc.createTextNode(text);
        parent.appendChild(res);
        return res;
    }


    const all_tags_c = child(cont, 'div');
    const items = child(cont, 'ul');
    items.id = 'visits';


    // TODO why has this ended up serialised??
    const visits = response.visits.map(rvisit =>
        new Visit(
            new Date(rvisit.time),
            rvisit.tags,
            rvisit.context,
            rvisit.locator,
        ) // TODO ugh ugly..
    );
    visits.sort((f, s) => (s.time - f.time));

    // move visits with contexts on top
    const with_ctx = [];
    const no_ctx = [];
    for (const v of visits) {
        if (v.context === null) {
            no_ctx.push(v);
        } else {
            with_ctx.push(v);
        }
    }

    // TODO FIXME instead, use checkboxes and get checked values
    // TODO not sure if should ignore things without contexts here... how to fit everything?
    const all_tags = new Set();
    for (const v of with_ctx) {
        for (const t of v.tags) {
            all_tags.add(t);
        }
    }

    for (let tag of [null, ...Array.from(all_tags).sort()]) {
        let predicate: ((string) => boolean);
        if (tag === null) {
            // meh
            tag = 'all';
            predicate = t => true;
        } else {
            predicate = t => t == tag;
        }

        // TODO show total counts?
        // TODO if too many tags, just overlap on the seconds line
        const tag_c = child(all_tags_c, 'span', ['tag', tag]);
        tchild(tag_c, tag);
        // TODO checkbox??
        tag_c.addEventListener('click', () => {
            for (const x of items.children) {
                const tt = unwrap(x.getAttribute('tags')).split(' ');
                const found = tt.some(predicate);
                x.style.display = found ? 'block' : 'none';
            }
        });
    }


    function handle(
        dates: string,
        times: string,
        tags: Array<Tag>,
        context: ?string=null,
        locator: ?Locator=null
    ) {

        const item = child(items, 'li');
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
        tchild(time_c, times);

        /* TODO locator could jump into the file? */
        if (context != null) {
            const ctx_c = child(item, 'div', ['context']);
            for (const line of context.split('\n')) {
                tchild(ctx_c, line);
                child(ctx_c, 'br');
            }

            const loc = unwrap(locator);
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
    }

    // TODO colors for sources would be nice... not sure if server or client provided
    for (const v of with_ctx) {
        const [dates, times] = _fmt(v.time);
        handle(dates, times, v.tags, v.context, v.locator);
    }


    var groups = [];
    var group = [];

    function dump_group () {
        if (group.length > 0) {
            groups.push(group);
            group = [];
        }
    }

    const delta = 20 * 60 * 1000;
    for (const v of no_ctx) {
        const last = group.length == 0 ? v : group[group.length - 1];
        if (last.time - v.time > delta) {
            dump_group();
        }
        group.push(v);
    }
    dump_group();

    const tag_map = opts.tag_map;
    // TODO group ones with no ctx..
    for (const group of groups) {
        const first = group[0];
        const last  = group[group.length - 1];
        const [fdates, ftimes] = _fmt(first.time);
        const [ldates, ltimes] = _fmt(last.time);
        const dates = ldates;
        const times = ltimes == ftimes ? ltimes : ltimes + "-" + ftimes;
        const tset = new Set();
        for (const v of group) {
            for (const tag of v.tags) {
                const mapped_tag = get_or_default(tag_map, tag, tag);
                tset.add(mapped_tag);
            }
        }
        const tags = [...tset];
        handle(dates, times, tags);
    }
}
window.bindSidebarData = bindSidebarData;

// TODO ugh, it actually seems to erase all the class information :( is it due to message passing??
function requestVisits() {
    chrome.runtime.sendMessage({
        method: 'getActiveTabVisits'
    }, (response)  => {
        if (response == null) {
            console.log("No visits for this url");
            return;
        }
        bindSidebarData(response);
   });
}


function boot() {
    const sidebar = document.createElement('div');
    sidebar.id = SIDEBAR_ID;
    // $FlowFixMe
    document.body.appendChild(sidebar);

    const App = (
            <Frame/>
    );

    ReactDOM.render(App, sidebar);
    requestVisits();
}

// TODO hmm maybe I don't need any of this iframe crap??
// https://stackoverflow.com/questions/5132488/how-to-insert-script-into-html-head-dynamically-using-javascript
