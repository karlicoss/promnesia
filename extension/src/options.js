/* @flow */
import type {Src} from './common';
import {getBrowser} from './common'

// $FlowFixMe
import OptionsSync from 'webext-options-sync';

type SrcMap = {
    [Src]: Src
};

export type Options = {
    host: string;
    token: string;


    verbose_errors_on: boolean;
    contexts_popup_on: boolean;

    highlight_on: boolean;

    dots: boolean;
    // this is kept as string to preserve formatting and comments
    blacklist: string;
    src_map: SrcMap;

    /* NOTE: a bit misleading name; it keeps all style settings now */
    position_css: string;

    /* NOTE: deprecated, perhaps should merge together with position_css and migrate propely */
    extra_css: string;

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
function defaultOptions(): Options {
    return {
        host: 'http://localhost:13131',
        token: '',

        verbose_errors_on: false,
        contexts_popup_on: false,

        highlight_on: true,

        dots: true,
        blacklist: '',
        src_map: {},


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
    return await optSync().getAll();
}

// TODO legacy; remove
export async function get_options_async() {
    return await getOptions();
}

/*
function sleeper(ms) {
    return function(x) {
        return new Promise(resolve => setTimeout(() => resolve(x), ms));
    };
}
*/

export async function setOptions(opts: Options) {
    const os = optSync();
    await os.set(opts);
}
