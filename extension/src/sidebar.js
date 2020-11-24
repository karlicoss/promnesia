/* @flow */
import {Visits, Visit, unwrap, format_duration, Methods, addStyle, Ids} from './common'
import type {Second} from './common'
import {getOptions, USE_ORIGINAL_TZ, GROUP_CONSECUTIVE_SECONDS} from './options';
import type {Options} from './options';
import {Binder, _fmt, asClass} from './display';
import {defensify} from './notifications';
import {achrome} from './async_chrome'

// TODO how to prevent sidebar hiding on click??

// TODO move to common?
function get_or_default(obj, key, def) {
    const res = obj[key];
    return res === undefined ? def : res;
}


const SIDEBAR_ID   = 'promnesia-sidebar';
const CONTAINER_ID = 'promnesia-sidebar-container';


const Cls = {
    /* marks the highlighted block of text */
    HIGHLIGHT: 'promnesia-highlight',
    /* points to the visit/context that caused the highlight */
    HIGHLIGHT_REF: 'promnesia-highlight-reference',
    /* just a wrapper trick to force it not take any space */
    HIGHLIGHT_REF_WRAPPER: 'promnesia-highlight-reference-wrapper',
}


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
            const show_dots_button = cdoc.createElement('button');
            show_dots_button.appendChild(cdoc.createTextNode('Mark visited'));
            // TODO hmm. not sure if defensify is gonna work from here? no access to notifications api?
            show_dots_button.addEventListener('click', defensify(async () => {
                await achrome.runtime.sendMessage({method: Methods.MARK_VISITED});
            }, 'mark_visited.onClick'));
            // TODO maybe highlight or just use custom class for that?
            show_dots_button.title = "Mark visited links on the current page with dots";
            cbody.appendChild(show_dots_button);
        }
        {
            const searchb = cdoc.createElement('button');
            searchb.appendChild(cdoc.createTextNode('Search'));
            searchb.addEventListener('click', defensify(async () => {
                await achrome.runtime.sendMessage({method: Methods.OPEN_SEARCH});
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
        // NOTE: this is idempotent and should be this way
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
        // apparently iframe is loading about:blank


        // TODO perhaps better move it to toggle? although maybe not necessary at all

        // TODO surely this is not necessary considering we do it anyway in bindSidebarData?
        // unless there is some sort of race condition?
        // requestVisits();


        return sidebar;
    }

}

async function sidebar(): Promise<Sidebar> {
    const opts = await getOptions()
    return new Sidebar(opts)
}


function _sanitize(text: string): string {
    /* cleanup to make matches more robust */
    // eslint-disable-next-line no-useless-escape
    return text.replace(/[.,\/#!$%\^&\*;:{}=\-_`~()]/g,'')
               .replace(/\s\s+/g, ' ')
               .trim();
}

// yields all DOM nodes that matched against some of the lines
function* findMatches(elem: Node, lines: Set<string>): Iterable<[string, Node]> {
    // first try to highlight the most specific element possible
    const children = elem.childNodes || []
    let found = false
    for (let c of children) {
        for (const m of findMatches(c, lines)) {
            found = true
            yield m
        }
    }
    if (found) {
        // some of the children matched.. so no need to process the element itself?
        return
    }
    // todo would be nice to cache it between highlight calls?
    // maybe just set on the element?
    const stext = _sanitize(elem.textContent)
    let matched = null
    for (const line of lines) {
        if (stext.includes(line)) {
            matched = line // make sure we break from the loop first so the iterator isn't invalidated
            break
        }
    }
    if (matched != null) {
        // no need to process it further
        lines.delete(matched)
        yield [matched, elem]
    }
}

// TODO potentially not very effecient; replace with something existing (Hypothesis??)
function _highlight(text: string, idx: number, v: Visit) {
    const lines = new Set()
    for (const line of text.split('\n')) {
        let sline = line.trim()
        if (sline.length == 0) {
            continue // no need to log
        }
        sline = _sanitize(line)
        if (sline.length <= 3) {
            console.debug("promnesia: line '%s' was completely sanitized/too short.. skipping", line)
            continue
        }
        lines.add(sline)
    }

    // TODO make sure they are unique? so we don't hl the same element twice..
    const to_hl = []
    for (let [line, target] of findMatches(unwrap(doc.body), lines)) {
        // https://developer.mozilla.org/en-US/docs/Web/API/Node/nodeType#Node_type_constants
        while (target != null && target.nodeType != Node.ELEMENT_NODE) {
            target = target.parentElement
        }

        if (target == null) {
            // eh. only text nodes are present, can't attach highlight to anything
            continue
        }
        target = ((target: any): HTMLElement)

        if (target.classList.contains(Cls.HIGHLIGHT)) {
            continue // shouldn't act on self
        }

        if (target.classList.contains('toastify')) {
            // hacky.. to avoid a race condition when toast notification is shown
            continue
        }

        // TODO why doesn't flow warn about this??
        // target.name === 'body'
        if (target === doc.body) {
            // meh, but otherwise too spammy
            console.debug('promnesia: body matched for highlight; skipping it')
            continue;
        }
        const d = unwrap(document.documentElement)
        const rect = target.getBoundingClientRect()
        const ratio = (rect.width * rect.height) / (d.scrollWidth * d.scrollHeight)
        const RATIO = 0.5 // kinda arbitrary
        if (ratio > RATIO) {
            console.warn('promnesia: matched element %o is too big (ratio %f > %f). skipping it', target, ratio, RATIO)
            continue
        }
        console.debug("promnesia: '%s': matched %o", line, target)

        // defer changing DOM to avoid reflow? not sure if actually an issue but just in case..
        // https://gist.github.com/paulirish/5d52fb081b3570c81e3a
        to_hl.push(target)
    }
    for (const target of to_hl) {
        // NOTE: there is <mark> tag, but it doesn't do anything apart from
        // so perhaps best to keep the DOM intact
        target.classList.add(Cls.HIGHLIGHT)

        const refc = doc.createElement('span')
        refc.classList.add(Cls.HIGHLIGHT_REF_WRAPPER)
        refc.classList.add('nonselectable')
        refc.style.width  = '0px'
        refc.style.height = '0px'
        refc.style.position = 'absolute'

        const ref = doc.createElement('span');
        ref.classList.add(Cls.HIGHLIGHT_REF);
        ref.textContent = String(idx)
        ref.title = `promnesia #${idx}: ${v.tags.join(' ')} ${(USE_ORIGINAL_TZ ? v.dt_local : v.time).toLocaleString()}`
        ref.style.position = 'relative'
        refc.appendChild(ref)

        target.insertAdjacentElement('beforeend', refc);
    }
}

function tryHighlight(text: string, idx: number, v: Visit) {
    // todo sidebar could also display if highlight matched or if it's "orphaned"
    // TODO use tag color for background?
    try {
        _highlight(text, idx, v)
    } catch (error) {
        console.error('promnesia: while highlighting %s %o: %o', text, v, error)
    }
}


/**
 * yields UI updates, so it's possible to schedule them in blocks and avoid blocking
 */
// TODO ugh. how to profile it? how to make sure it can never slow down user UI?
async function* _bindSidebarData(response: Visits) {
    // TODO ugh. we probably only want to set data, don't want to do anything with dom until we trigger the sidebar?
    // TDO perhaps we need something reactive...
    // window.sidebarData = response;
    const opts = await getOptions();
    const sidebar = new Sidebar(opts);

    const cont = await sidebar.getContainer();
    await sidebar.clear(); // TODO probably, unnecessary?

    // a way to ensure the sidebar rendering isn't impacting the browsing experience
    // TODO use the same logic in search?
    const YIELD_DELAY_MS = 200
    let last_yield = 0
    let iterations_since = 0
    function shouldYield() {
        let cur = new Date().getTime()
        iterations_since += 1
        const took = cur - last_yield
        if (took < YIELD_DELAY_MS) {
            return false
        }
        // todo eh, would be nice to log something more useful here..
        console.debug('promnesia: bindSidebarData: %d iterations passed, took %o ms', iterations_since, took)
        last_yield = cur
        iterations_since = 0
        return true
    }
    //

    const binder = new Binder(doc, opts)

    const all_tags_c = binder.makeChild(cont, 'div', ['src-filter']);
    const items = binder.makeChild(cont, 'ul');
    items.id = Ids.VISITS

    const [visits, errors] = response.partition()
    const normalised = response.normalised_url

    for (const err of errors) {
        await binder.renderError(items, err)
    }

    visits.sort((f, s) => {
        // keep 'relatives' in the bottom
        // TODO: this might slightly break local visits sorting, becuase they don't necessarily have proper normalisation
        const fr = f.normalised_url === normalised
        const sr = s.normalised_url === normalised
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
            // TODO https://github.com/karlicoss/promnesia/issues/132
            // maybe just reorder them and show after visits with context?
            // meh
            tag = 'all';
            predicate = () => true;
        } else {
            predicate = t => t == tag;
        }

        // TODO show total counts?
        // TODO if too many tags, just overlap on the seconds line
        const tag_c = binder.makeChild(all_tags_c, 'span', ['src', asClass(tag)])
        binder.makeTchild(tag_c, `${tag} (${count})`);
        // TODO checkbox??
        tag_c.addEventListener('click', () => {
            for (const x of items.children) {
                const sources = unwrap(x.dataset['sources']).split(' ');
                const found = sources.some(predicate);
                x.style.display = found ? 'block' : 'none';
            }
        });
    }

    const visit_date_time = (v: Visit) => _fmt(USE_ORIGINAL_TZ ? v.dt_local : v.time)

    const entries = with_ctx.entries() // NOTE: it's an iterator
    /*
     * ugh. hacky way to defer UI thread updating... otherwise it blocks the interface on too many visits
     * TBH this is a beat stupid... surely async style execution would be super useful for this, why is it not here by default?
     */
    for (const [idx0, v] of entries) {
        if (shouldYield()) {
            yield
        }
        const idx1 = idx0 + 1; // eh, I guess that makes more sense for humans
        const ctx = unwrap(v.context);

        // TODO hmm. hopefully chrome visits wouldn't get highlighted here?
        const relative = v.normalised_url != normalised

        if (!relative && opts.highlight_on) {
            // todo this might compete for execution with the sidebar rendering...
            // later maybe integrate it in the yield mechanism..
            setTimeout(() => tryHighlight(ctx, idx1, v))
        }

        // TODO maybe shouldn't attach immediately? not sure
        const [dates, times] = visit_date_time(v)
        binder.render(items, dates, times, v.tags, {
            idx           : idx1,
            timestamp     : v.time,
            original_url  : v.original_url,
            normalised_url: null, // hmm, looks like i'm relying on normalised set to null..
            context       : v.context,
            locator       : v.locator,
            relative      : relative,
        })
    }

    const delta_ms = GROUP_CONSECUTIVE_SECONDS * 1000;
    function* groups() {
        let group = [];
        for (const v of no_ctx) {
            const last = group.length == 0 ? v : group[group.length - 1];
            const diff = last.time - v.time
            if (diff > delta_ms) {
                if (group.length > 0) {
                    yield group;
                }
                group = []
            }
            group.push(v);
        }
        if (group.length > 0) {
            yield group;
        }
    }

    // todo maybe it should be a generic hook instead?
    // todo how to make it defensive?..
    const tag_map = JSON.parse(opts.src_map)
    for (const group of groups()) {
        if (shouldYield()) {
            yield // give way to UI thread
        }
        const first = group[0];
        const last  = group[group.length - 1];
        // eslint-disable-next-line no-unused-vars
        const [fdates, ftimes] = visit_date_time(first)
        const [ldates, ltimes] = visit_date_time(last)
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
        await binder.render(items, dates, times, tags, {
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

async function bindSidebarData(response: Visits) {
    const dom_updates_gen = _bindSidebarData(response)
    async function consume_one() {
        // consume head
        const res = await dom_updates_gen.next()
        if (!res.done) {
            // schedule tail
            setTimeout(consume_one)
        }
    }
    await consume_one()
}



// TODO ugh, it actually seems to erase all the class information :( is it due to message passing??
// eslint-disable-next-line no-unused-vars
function requestVisits(): void {
    achrome.runtime.sendMessage({method: Methods.GET_SIDEBAR_VISITS})
           .then((response: {}) => {
               if (response == null) {
                   // todo why would it be?
                   return
               }
               bindSidebarData(Visits.fromJObject(response))
           })
}


// eslint-disable-next-line no-unused-vars
chrome.runtime.onMessage.addListener((msg: any, sender: chrome$MessageSender) => {
    const method = msg.method
    if        (method == Methods.BIND_SIDEBAR_VISITS) {
        bindSidebarData(Visits.fromJObject(msg.data))
    } else if (method == Methods.SIDEBAR_SHOW) {
        sidebar().then(s => s.show())
    } else if (method == Methods.SIDEBAR_TOGGLE) {
        sidebar().then(s => s.toggle())
    }
    // todo do I need to return anything?
})

// TODO make configurable? or resizable?

// TODO shit. if it's not an iframe can't be scrollable?

// TODO hmm maybe I don't need any of this iframe crap??
// https://stackoverflow.com/questions/5132488/how-to-insert-script-into-html-head-dynamically-using-javascript
