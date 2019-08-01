/* @flow */
import {Visits, Visit, unwrap, format_duration, Methods} from './common';
import type {Second} from './common';
import {get_options_async} from './options';
import type {Options} from './options';
import {Binder, _fmt} from './display';

// TODO how to prevent sidebar hiding on click??

// TODO move to common?
function get_or_default(obj, key, def) {
    const res = obj[key];
    return res === undefined ? def : res;
}


const SIDEBAR_ID = "wereyouhere-sidebar";
const sidebar_width = '500px'; // TODO get from settings?

const doc = document;

class Sidebar {
    body: HTMLBodyElement;
    opts: Options;

    constructor(opts: Options) {
        this.body = unwrap(doc.body);
        this.opts = opts;
    }

    getContainer(): HTMLElement {
        const frame = unwrap(this.getFrame());

        // TODO wtf?? adding styles didn't work on iframe createion (in ensureFrame method)
        const cdoc = frame.contentDocument;
        const head = unwrap(cdoc.head);

        const sidebar_css = chrome.extension.getURL("sidebar.css");
        const link = cdoc.createElement("link");
        link.href = sidebar_css;
        link.type = "text/css";
        link.rel = "stylesheet";
        head.appendChild(link);

        const style = cdoc.createElement('style');
        style.innerHTML = this.opts.extra_css;
        head.appendChild(style);

        // make links open in new tab instead of iframe https://stackoverflow.com/a/2656798/706389
        const base = cdoc.createElement('base');
        base.setAttribute('target', '_blank');
        head.appendChild(base);

        return unwrap(frame.contentDocument.body);
    }

    clear() {
        // TODO not sure if that's even necessary?
        const cont = this.getContainer();
        while (cont.firstChild) {
            cont.removeChild(cont.firstChild);
        }
    }

    toggle() {
        if (this.shown()) {
            this.hide();
        } else {
            this.show();
        }
    }

    shown(): boolean {
        const frame = this.getFrame();
        if (frame == null) {
            return false;
        }
        return frame.style.display === 'block'; // TODO not sure...
    }

    show() {
        const frame = this.ensureFrame();

        // TODO FIXME when should we bind data?
        const original_padding = this.body.style.paddingRight;
        this.body.setAttribute('original_padding', original_padding);
        this.body.style.paddingRight = sidebar_width;
        frame.style.display = 'block';
    }

    hide() {
        const frame = this.ensureFrame();

        // const original_padding = unwrap(this.body.getAttribute('original_padding'));
        // TODO FIXME why that doesn't work??
        const original_padding = '';
        this.body.style.paddingRight = original_padding;
        frame.style.display = 'none';
    }

    getFrame(): ?HTMLIFrameElement {
        return ((doc.getElementById(SIDEBAR_ID): any): ?HTMLIFrameElement);
    }

    ensureFrame(): HTMLIFrameElement {
        const frame = this.getFrame();
        if (frame != null) {
            return frame;
        }

        const sidebar = doc.createElement('iframe'); this.body.appendChild(sidebar);
        sidebar.src = '';
        sidebar.id = SIDEBAR_ID;

        for (let [key, value] of Object.entries({
            'position'  : 'fixed',
            'right'     : '0px',
            'top'       : '0px',
            'z-index'   : '9999',
            'width'     : sidebar_width,
            'height'    : '100%',
            'background': 'rgba(236, 236, 236, 0.4)',
        })) {
            // $FlowFixMe
            sidebar.style.setProperty(key, value);
        }

        requestVisits(); // TODO not sure that belongs here...
        return sidebar;
    }

}

async function sidebar(): Promise<Sidebar> {
    const opts = await get_options_async();
    return new Sidebar(opts);
}

async function toggleSidebar() {
    (await sidebar()).toggle();
}
// to make function available for executeScript... gross
window.toggleSidebar = toggleSidebar;


async function bindSidebarData(response) {
    const opts = await get_options_async();
    const sidebar = new Sidebar(opts);

    const cont = sidebar.getContainer();
    sidebar.clear(); // TODO probably, unnecessary?
    console.log(response);

    const binder = new Binder(doc);


    const all_tags_c = binder.makeChild(cont, 'div', ['tag-filter']);
    const items = binder.makeChild(cont, 'ul');
    items.id = 'visits';


    // TODO why has this ended up serialised??
    const visits = response.visits.map(rvisit =>
        new Visit(
            rvisit.original_url,
            rvisit.normalised_url,
            new Date(rvisit.time),
            rvisit.tags,
            rvisit.context,
            rvisit.locator,
            rvisit.duration,
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
    const all_tags = new Map();
    for (const v of with_ctx) {
        for (const t of v.tags) {
            const pv = (all_tags.has(t) ? all_tags.get(t) : 0) + 1;
            all_tags.set(t, pv);
        }
    }

    binder.makeTchild(all_tags_c, 'filter: ');
    for (let [tag, count] of [[null, with_ctx.length], ...Array.from(all_tags).sort()]) {
        let predicate: ((string) => boolean);
        if (tag === null) {
            // meh
            tag = 'all';
            predicate = () => true;
        } else {
            predicate = t => t == tag;
        }

        // TODO show total counts?
        // TODO if too many tags, just overlap on the seconds line
        const tag_c = binder.makeChild(all_tags_c, 'span', ['tag', tag]);
        binder.makeTchild(tag_c, `${tag} (${count})`);
        // TODO checkbox??
        tag_c.addEventListener('click', () => {
            for (const x of items.children) {
                const tt = unwrap(x.getAttribute('tags')).split(' ');
                const found = tt.some(predicate);
                x.style.display = found ? 'block' : 'none';
            }
        });
    }


    for (const v of with_ctx) {
        const [dates, times] = _fmt(v.time);
        binder.render(items, dates, times, v.tags, {
            timestamp     : v.time,
            original_url  : null,
            normalised_url: null,
            context       : v.context,
            locator       : v.locator,
        });
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
        // eslint-disable-next-line no-unused-vars
        const [fdates, ftimes] = _fmt(first.time);
        const [ldates, ltimes] = _fmt(last.time);
        const dates = ldates;
        const times = ltimes == ftimes ? ltimes : ltimes + "-" + ftimes;
        const tset = new Set();
        let total_dur: ?Second = null;
        for (const v of group) {
            if (v.duration !== null) {
                if (total_dur === null) {
                    total_dur = 0;
                }
                total_dur += v.duration;
            }
            for (const tag of v.tags) {
                const mapped_tag = get_or_default(tag_map, tag, tag);
                tset.add(mapped_tag);
            }
        }
        const tags = [...tset].sort();
        const ctx = total_dur == null ? null : `Time spent: ${format_duration(total_dur)}`;
        binder.render(items, dates, times, tags, {
            timestamp: first.time,
            original_url  : null,
            normalised_url: null,
            context: ctx,
            locator: null,
        });
    }
}
window.bindSidebarData = bindSidebarData;

// TODO ugh, it actually seems to erase all the class information :( is it due to message passing??
function requestVisits() {
    chrome.runtime.sendMessage({
        method: Methods.GET_SIDEBAR_VISITS,
    }, (response: ?Visits)  => {
        if (response == null) {
            console.log("No visits for this url");
            return;
        }
        bindSidebarData(response);
   });
}


// TODO make configurable? or resizable?

// TODO shit. if it's not an iframe can't be scrollable?

// TODO hmm maybe I don't need any of this iframe crap??
// https://stackoverflow.com/questions/5132488/how-to-insert-script-into-html-head-dynamically-using-javascript
