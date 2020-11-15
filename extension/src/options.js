/* @flow */
import {getBrowser} from './common'

// $FlowFixMe
import OptionsSync from 'webext-options-sync';


export type Options = {|
    host: string;
    token: string;

    use_bookmarks     : boolean,

    use_browserhistory: boolean,
    browserhistory_max_results: number,

    verbose_errors_on: boolean;
    contexts_popup_on: boolean;
    sidebar_always_show: boolean,
    sidebar_detect_urls: boolean;

    highlight_on: boolean;

    always_mark_visited: boolean;
    // this is kept as string to preserve formatting and comments
    blacklist: string;
    // kept as string to preserve formatting
    filterlists: string;
    src_map    : string;

    /* NOTE: a bit misleading name; it keeps all style settings now */
    position_css: string;

    /* NOTE: deprecated, perhaps should merge together with position_css and migrate propely */
    extra_css: string;

|}

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
function defaultOptions(): Options {
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
        sidebar_always_show: false,

        highlight_on: true,

        always_mark_visited: false,
        blacklist: '',
        // todo would be nice to validate on saving...
        filterlists: `[
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
/* you can use devtools to find other CSS you can tweak */

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

export async function getOptions(): Promise<Options> {
    const r = await optSync().getAll()
    let smap = r.src_map
    if (typeof smap !== 'string') {
        // old format, we used to keep as a map
        smap = JSON.stringify(smap)
    }
    r.src_map = smap
    return r
}

export async function setOptions(opts: Options) {
    const os = optSync();
    await os.set(opts);
}
