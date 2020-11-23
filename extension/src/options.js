/* @flow */
import {getBrowser} from './common'

// $FlowFixMe
import OptionsSync from 'webext-options-sync';



/* NOTE: options can only be renamed in-between store releases */
/* maybe later will bother with migrations for consistent naming, but that would require tests first */

// ugh. hacky way to support partial option setting...
type Opt1 = {|
    mark_visited_excludelist: string;
|}

type Opt2 = {|
    // this is kept as string to preserve formatting and comments
    blacklist: string;
|}

type IndeterminateMixin = {|
    sidebar_always_show: ?boolean,
    mark_visited_always: ?boolean,
|}

type Mixin = {|
    sidebar_always_show: boolean,
    mark_visited_always: boolean,
|}

type BaseOptions = {|
    host: string;
    token: string;

    use_bookmarks     : boolean,

    use_browserhistory: boolean,
    browserhistory_max_results: number,

    verbose_errors_on: boolean;
    contexts_popup_on: boolean;
    sidebar_detect_urls: boolean;

    highlight_on: boolean;


    ...Opt1,
    ...Opt2,


    // kept as string to preserve formatting
    global_excludelists_ext: string;


    // todo need to document this...
    src_map    : string;

    /* NOTE: a bit misleading name; it keeps all style settings now */
    position_css: string;

    /* NOTE: deprecated, perhaps should merge together with position_css and migrate propely */
    extra_css: string;

|}


export type StoredOptions = {|
    ...BaseOptions,
    ...IndeterminateMixin,
|}


export type Options = {
    ...BaseOptions,
    ...Mixin,
}

/*
 * If true , keep ghe original timezone (stored in the database)
 * If false, convert to the browser's timezone
 *
 * Example: Imagine you have a database visit made at 2001-02-03 10:00:00 California time, and your browser is in NY time
 * If true , extension will display the visit at 2001-02-03 10:00:00
 * If false, extension will display the visit at 2001-02-03 13:00:00
 * TODO: later add it to the options interface?
 */
export const USE_ORIGINAL_TZ = true;

export const GROUP_CONSECUTIVE_SECONDS = 20 * 60;

// TODO: make it configurable in options?
export const THIS_BROWSER_TAG = getBrowser()

// TODO allow to export settings
// https://github.com/fregante/webext-options-sync/issues/23
function defaultOptions(): StoredOptions {
    return {
        host: 'http://localhost:13131',
        token: '',

        use_bookmarks     : true,

        use_browserhistory: true,
        browserhistory_max_results: 10000,

        // todo might be nice to have some of these none to tell apart from default set by me, or user set...

        verbose_errors_on: false,
        contexts_popup_on: false,
        sidebar_detect_urls: true,
        sidebar_always_show: null,

        highlight_on: true,

        mark_visited_always     : null,
        mark_visited_excludelist: '',

        blacklist: '',
        // todo would be nice to validate on saving...
        global_excludelists_ext: `[
  ["Webmail",
   "https://raw.githubusercontent.com/cbuijs/shallalist/master/webmail/domains"        ],
  ["Banking",
   "https://raw.githubusercontent.com/cbuijs/shallalist/master/finance/banking/domains"]
]`,
        src_map: '{}',


        /* Change these if you want to reposition the sidebar
         * E.g. to display on bottom, use :root { --bottom 1; --size: 25%; }
         * TODO shit, somehow this was breaking on Android... I guess keep it aside
         */

        // TODO tooltip??

        // TODO do something defensive if value ended up as invalid?..
        // TODO make it literate from test?
        // TODO hmm. not sure if I can get rid of :root thing without relying on JS?
        // TODO would be nice to use true/false, but that prob. won't work
        // TODO add docs on positioning
        // TODO eh, would be nice to make it work with --right: true. right now it doesn't
        position_css: `
/* you can use devtools to find other CSS attributes you can tweak */

/* tweak sidebar position/size/style */
#promnesia-sidebar {
    /* you can also use
       --left/--top/--bottom
       to change the sidebar position */
    --right: 1;

    --size: 30%;

    /* you can also use any other valid CSS
       easiest is to experiment in devtools first */
    background-color: rgba(236, 236, 236, 0.8);
}

/* tweak elements within the sidebar */
#promnesia-sidebar .src {
    font-weight: bold;
}


/* tweak 'visited' marks: specify hex color here */
:root {
  --promnesia-src-sourcename-color: #ff00ff;
  /* e.g.
  --promnesia-src-reddit-color: #ff0000;
  or
  --promnesia-src-twitter-color: #0000ff;
   */
}


/* uncomment to override/tweak 'visited' marks */
/*
.promnesia-visited {
    border: dashed green;
}

.promnesia-visited:after {
    content: "" !important;
}
*/

/* uncomment to override/tweak highlights */
/*
.promnesia-highlight {
   background-color: green !important;
}

.promnesia-highlight-reference {
   color: red !important;
}
*/
`.trim(),

/* uncomment this to suppress the notification popup
   (will be more tweakable in the future)
   .toastify {
     display: none !important;
   }
*/
        // NOTE: deprecated
        extra_css   : '',
    };
}


// TODO mm. don't really like having global object, but seems that it's easiest way to avoid race conditions
// TODO https://github.com/fregante/webext-options-sync/issues/38 -- fixed now
const _options = new OptionsSync({
    defaults: defaultOptions(),
});


function optSync() {
    return _options;
}

// gets the actual raw values that user set, just for the options page
export async function getStoredOptions(): Promise<StoredOptions> {
    const r = await optSync().getAll()
    let smap = r.src_map
    if (typeof smap !== 'string') {
        // old format, we used to keep as a map
        smap = JSON.stringify(smap)
    }
    r.src_map = smap
    return r
}


// gets overlay move suitable for use in the business logic
export async function getOptions(): Promise<Options> {
    const stored = await getStoredOptions()
    // extension dependent defaults
    const devDefaults: Mixin = {
        sidebar_always_show: stored.sidebar_always_show == null ? false : stored.sidebar_always_show,
        mark_visited_always: stored.mark_visited_always == null ? false : stored.mark_visited_always,
    }
    return {...stored, ...devDefaults}
}


// TODO would be nice to accept a substructure of Options??
export async function setOptions(opts: StoredOptions) {
    const os = optSync()
    await os.set(opts)
}

export async function setOption(opt: Opt1 | Opt2) {
    const os = optSync()
    await os.set(opt)
}

export async function resetOptions() {
    const os = optSync()
    await os.setAll({})
}

function toggleOption(toggle: (StoredOptions) => void): () => Promise<void> {
    return async () => {
        const opts = await getStoredOptions()
        toggle(opts)
        await setOptions(opts)
    }
}

export const Toggles = {
    showSidebar   : toggleOption((opts) => { opts.sidebar_always_show = !opts.sidebar_always_show; }),
    markVisited   : toggleOption((opts) => { opts.mark_visited_always = !opts.mark_visited_always; }),
    showHighlights: toggleOption((opts) => { opts.highlight_on        = !opts.highlight_on       ; }),
}

// TODO try optionsStorage.syncForm?
