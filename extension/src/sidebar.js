/* @flow */
import {Visits, Visit, unwrap, format_duration, Methods, addStyle} from './common';
import type {JsonObject, Second} from './common';
import {get_options_async} from './options';
import type {Options} from './options';
import {Binder, _fmt} from './display';
import {defensify} from './notifications';
import {chromeRuntimeSendMessage} from './async_chrome';

// TODO how to prevent sidebar hiding on click??

// TODO move to common?
function get_or_default(obj, key, def) {
    const res = obj[key];
    return res === undefined ? def : res;
}


const SIDEBAR_ID   = 'promnesia-sidebar';
const CONTAINER_ID = 'promnesia-sidebar-container';

const SIDEBAR_ACTIVE = 'promnesia';

const doc = document;

// TODO think about 'show dots' and 'search' icons -- maybe only show them for android?
class Sidebar {
    body: HTMLBodyElement;
    opts: Options;

    constructor(opts: Options) {
        this.body = unwrap(doc.body);
        this.opts = opts;
    }

    async getContainer(): Promise<HTMLElement> {
        const frame = await this.ensureFrame();
        return unwrap(frame.contentDocument.getElementById(CONTAINER_ID));
    }

    setupFrame(frame) {
        const cdoc = frame.contentDocument;
        const head = unwrap(cdoc.head);

        const sidebar_css = chrome.extension.getURL("sidebar.css");
        const link = cdoc.createElement("link");
        link.href = sidebar_css;
        link.type = "text/css";
        link.rel = "stylesheet";
        head.appendChild(link);

        addStyle(cdoc, this.opts.position_css);

        // make links open in new tab instead of iframe https://stackoverflow.com/a/2656798/706389
        const base = cdoc.createElement('base');
        base.setAttribute('target', '_blank');
        head.appendChild(base);

        const cbody = unwrap(cdoc.body);
        // TODO not sure if it should be same as SIDEBAR_ACTIVE thing?
        cbody.classList.add('promnesia');
        // it's a bit hacky.. but stuff inside and outside iframe got different namespace, so ok to reuse id?
        // makes it much easier for settings
        cbody.id = SIDEBAR_ID;
        {
            const show_dots = cdoc.createElement('button');
            show_dots.appendChild(cdoc.createTextNode('Mark visited'));
            show_dots.addEventListener('click', defensify(async () => {
                await chromeRuntimeSendMessage({method: Methods.MARK_VISITED});
            }, 'mark_visited.onClick'));
            // TODO maybe highlight or just use custom class for that?
            show_dots.title = "Mark visited links on the current page with dots";
            cbody.appendChild(show_dots);
        }
        {
            const searchb = cdoc.createElement('button');
            searchb.appendChild(cdoc.createTextNode('Search'));
            searchb.addEventListener('click', defensify(async () => {
                await chromeRuntimeSendMessage({method: Methods.OPEN_SEARCH});
            }, 'open_search.onClick'));
            cbody.appendChild(searchb);
        }
        {
            // TODO only on mobile?
            const elem = cdoc.createElement('button');
            elem.appendChild(cdoc.createTextNode('Close'));
            elem.addEventListener('click', defensify(async () => {
                await this.hide();
            }, 'close_sidebar.onClick'));
            cbody.appendChild(elem);
        }
        /*
        {
            const hb = cdoc.createElement('button');
            hb.appendChild(cdoc.createTextNode('Highlight')); // TODO eh, not sure ... need a proper component for that or what?

        }
        */ // TODO notsure about that...

        const ccc = cdoc.createElement('div');
        ccc.id = CONTAINER_ID;
        cbody.appendChild(ccc);
    }

    async clear() {
        // TODO not sure if that's even necessary?
        const cont = await this.getContainer();
        while (cont.firstChild) {
            cont.removeChild(cont.firstChild);
        }
    }

    async toggle() {
        if (await this.shown()) {
            await this.hide();
        } else {
            await this.show();
        }
    }

    async shown(): Promise<boolean> {
        const frame = await this.getFrame();
        if (frame == null) {
            return false;
        }
        return frame.style.display === 'block'; // TODO not sure...
    }

    async show() {
        const frame = await this.ensureFrame();
        this.body.classList.add(SIDEBAR_ACTIVE);
        frame.style.display = 'block';
    }

    async hide() {
        const frame = await this.ensureFrame();
        this.body.classList.remove(SIDEBAR_ACTIVE);
        frame.style.display = 'none';
    }

    getFrame(): ?HTMLIFrameElement {
        return ((doc.getElementById(SIDEBAR_ID): any): ?HTMLIFrameElement);
    }

    async ensureFrame(): Promise<HTMLIFrameElement> {
        const frame = this.getFrame();
        if (frame != null) {
            return frame;
        }

        const sidebar = doc.createElement('iframe'); this.body.appendChild(sidebar);
        sidebar.src = '';
        sidebar.id = SIDEBAR_ID;
        sidebar.classList.add(SIDEBAR_ACTIVE);


        // TODO ugh it's a bit ridiculous that because of single iframe I have to propagate async everywhere..
        const loadPromise = new Promise((resolve, /*reject*/) => {
            // TODO not sure if there is anything to reject?..
            sidebar.addEventListener('load', () => {resolve();}, {once: true});
        });
        await loadPromise;

        this.setupFrame(sidebar);

        // TODO a bit nasty, but at the moment easiest way to solve it
        // apparetnly iframe is loading about:blank 


        // TODO perhaps better move it to toggle? although maybe not necessary at all

        // TODO surely this is not necessary considering we do it anyway in bindSidebarData?
        // unless there is some sort of race condition?
        // requestVisits();


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


function findText(elem: Node, text: string): ?Node {
    let res = null;
    // TODO need to match or something..
    // TODO not sure if better to go bottom up?
    if (elem.textContent.includes(text)) {
        res = elem;
    }
    const children = elem.childNodes;
    if (children == null) {
        return res;
    }
    for (let x of children) {
        let cr = findText(x, text);
        if (cr != null) {
            return cr;
        }
    }
    return res;
}

// TODO not very effecient; replace with something existing (Hypothesis??)
function _highlight(text: string, idx: number) {
    for (const line of text.split('\n')) {
        // TODO filter too short strings? or maybe only pick the longest one?
        const found = findText(unwrap(doc.body), line);
        if (found == null) {
            console.debug('No match found for %s', line);
            continue;
        }
        console.debug("highlighting %o %s", found, line);

        // $FlowFixMe
        const target: HTMLElement = unwrap(found.nodeType == Node.TEXT_NODE ? found.parentElement : found);

        if (target.classList.contains('toastify')) {
            // TODO hacky...
            continue;
        }

        // TODO why doesn't flow warn about this??
        // target.name === 'body'
        if (target === doc.body) {
            // meh, but otherwise too spammy
            console.warn('body matched for highlight; skipping it');
            continue;
        }

        target.classList.add('promnesia-highlight');
        const ref = doc.createElement('span');
        ref.classList.add('promnesia-highlight-reference');
        ref.classList.add('nonselectable');
        ref.appendChild(doc.createTextNode(String(idx)));
        target.insertAdjacentElement('beforeend', ref);
    }
}

function tryHighlight(text: string, idx: number) {
    // TODO sidebar could also display if highlight matched or if it's "orphaned"
    // TODO use tag color for background?
    try {
        _highlight(text, idx);
    } catch (error) {
        console.error('Error while highlighting %s: %o', text, error); // TODO come up with something better..
    }
}

// used dynamically
// eslint-disable-next-line no-unused-vars
async function bindError(message: string) {
    const opts = await get_options_async();
    const sidebar = new Sidebar(opts);

    const cont = await sidebar.getContainer();
    await sidebar.clear(); // TODO probably, unnecessary?

    const binder = new Binder(doc);
    binder.error(cont, message);
}


// TODO rename to 'set'?
async function bindSidebarData(response: JsonObject) {
    // TODO ugh. we probably only want to set data, don't want to do anything with dom until we trigger the sidebar?
    // TDO perhaps we need something reactive...
    // window.sidebarData = response;
    const opts = await get_options_async();
    const sidebar = new Sidebar(opts);

    const cont = await sidebar.getContainer();
    await sidebar.clear(); // TODO probably, unnecessary?

    const binder = new Binder(doc);

    const all_tags_c = binder.makeChild(cont, 'div', ['src-filter']);
    const items = binder.makeChild(cont, 'ul');
    items.id = 'visits';


    // TODO why has this ended up serialised??
    const visits = response.visits.map(rvisit =>
        new Visit(
            rvisit.original_url,
            rvisit.normalised_url,
            new Date(rvisit.time), // TODO careful about utc here?
            rvisit.tags,
            rvisit.context,
            rvisit.locator,
            rvisit.duration,
        ) // TODO ugh ugly..
    );
    visits.sort((f, s) => {
        // keep 'relatives' in the bottom
        const fr = f.normalised_url === response.normalised_url;
        const sr = s.normalised_url === response.normalised_url;
        if (fr != sr) {
            return (sr ? 1 : 0) - (fr ? 1 : 0);
        }
        return s.time - f.time;
    });

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

    // TODO instead, use checkboxes and get checked values
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
        const tag_c = binder.makeChild(all_tags_c, 'span', ['src', tag]);
        binder.makeTchild(tag_c, `${tag} (${count})`);
        // TODO checkbox??
        tag_c.addEventListener('click', () => {
            for (const x of items.children) {
                const sources = unwrap(x.getAttribute('sources')).split(' ');
                const found = sources.some(predicate);
                x.style.display = found ? 'block' : 'none';
            }
        });
    }


    for (const [idx0, v] of with_ctx.entries()) {
        const idx1 = idx0 + 1; // eh, I guess that makes more sense for humans
        const ctx = unwrap(v.context);

        // TODO hmm. hopefully chrome visits wouldn't get highlighted here?
        const relative = v.normalised_url != response.normalised_url;

        if (!relative && opts.highlight_on) {
            tryHighlight(ctx, idx1);
        }


        const [dates, times] = _fmt(v.time);
        binder.render(items, dates, times, v.tags, {
            idx           : idx1,
            timestamp     : v.time,
            original_url  : v.original_url,
            normalised_url: null, // hmm, looks like i'm relying on normalised set to null..
            context       : v.context,
            locator       : v.locator,
            relative      : relative,
        });
    }


    function* groups() {
        let group = [];
        const delta = 20 * 60 * 1000;
        for (const v of no_ctx) {
            const last = group.length == 0 ? v : group[group.length - 1];
            if (last.time - v.time > delta) {
                if (group.length > 0) {
                    yield group;
                }
                group.length = 0
            }
            group.push(v);
        }
        if (group.length > 0) {
            yield group;
        }
        group.length = 0
    }

    const tag_map = opts.src_map;
    // TODO group ones with no ctx..
    for (const group of groups()) {

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
            idx: null,
            timestamp: first.time,
            original_url  : null,
            normalised_url: null,
            context: ctx,
            locator: null,
            relative: false,
        });
    }
}


// hmm. otherwise it can't be called from executescript??
window.bindSidebarData = bindSidebarData;
window.bindError       = bindError;

// TODO ugh, it actually seems to erase all the class information :( is it due to message passing??
// eslint-disable-next-line no-unused-vars
function requestVisits() {
    chromeRuntimeSendMessage({method: Methods.GET_SIDEBAR_VISITS})
        .then((response: ?Visits) => {
            if (response == null) {
                return;
            }
            bindSidebarData(response);
        });
}


// TODO make configurable? or resizable?

// TODO shit. if it's not an iframe can't be scrollable?

// TODO hmm maybe I don't need any of this iframe crap??
// https://stackoverflow.com/questions/5132488/how-to-insert-script-into-html-head-dynamically-using-javascript
