/* @flow */
import {unwrap} from './common';
import {getOptions, setOptions} from './options'
import {defensifyAlert, alertError} from './notifications';

// re: codemirror imports
// err. that's a bit stupid, js injected css? surely it can be done via webpack and static files...
// TODO right, I suppose that's why I need style bunder?
// turned out more tedious than expected... https://github.com/codemirror/CodeMirror/issues/5484#issue-338185331


// helpers for options
class Option<T> {
    id: string

    constructor(id: string) {
        this.id = id
    }

    set value(x: T): void {
        throw Error('Not implemented')
    }
    get value(): T {
        throw Error('Not implemented')
    }

    get element(): HTMLInputElement {
        return ((document.getElementById(this.id): any): HTMLInputElement);
    }
}

class Simple extends Option<string> {
    set value(x: string): void {
        this.element.value = x
    }

    get value(): string {
        return this.element.value
    }
}

class Toggle extends Option<boolean> {
    set value(x: boolean): void {
        this.element.checked = x
    }

    get value(): boolean {
        return this.element.checked
    }
}

class Editor extends Option<string> {
    mode: ?string
    constructor(id: string, {mode}) {
        super(id)
        this.mode = mode
    }

    set value(x: string): void {
        this.editor.setValue(x)
    }

    get value(): string {
        return this.editor.getValue()
    }

    bind({CodeMirror}): void {
        CodeMirror(this.element, {
            mode: this.mode,
            lineNumbers: true,
            value: 'FIXME default',
        })
    }

    get editor() {
        // $FlowFixMe
        return this.element.querySelector('.CodeMirror').CodeMirror
    }
}
// end

const o_host           = new Simple('host_id'               )
const o_token          = new Simple('token_id'              )
const o_verbose_errors = new Toggle('verbose_errors_id'     )
const o_contexts_popup = new Toggle('contexts_popup_id'     )
const o_detect_urls    = new Toggle('detect_sidebar_urls_id')
const o_highlights_on  = new Toggle('highlight_id'          )
// TODO ('dots_id');

const o_blacklist    = new Editor('blacklist_id'   , {mode: null  })
const o_filterlists  = new Editor('filterlists_id' , {mode: 'javascript'})
const o_src_map      = new Editor('source_map_id'  , {mode: 'javascript'})
const o_position_css = new Editor('position_css_id', {mode: 'css' })
const o_extra_css    = new Editor('extra_css_id'   , {mode: 'css' })


// TODO meh. not sure how to make sure it's only imported once?..
async function importCM() {
    // TODO I don't really understand, what's up with these fucking chunks and their naming
    // at least it reduces size of the options page
    const {default: CodeMirror} = await import(
        /* webpackChunkName: "codemirror-main" */
        // $FlowFixMe
        'codemirror/lib/codemirror.js'
    )
    // TODO just copy css in webpack directly??
    await import(
        /* webpackChunkName: "codemirror.css" */
        // $FlowFixMe
        'codemirror/lib/codemirror.css'
    )
    await import(
        /* webpackChunkName: "codemirror-css-module" */
        // $FlowFixMe
        'codemirror/mode/css/css.js'
    )
    await import(
        /* webpackChunkName: "codemirror-js-module" */
        // $FlowFixMe
        'codemirror/mode/javascript/javascript.js'
    )
    return CodeMirror
}

document.addEventListener('DOMContentLoaded', defensifyAlert(async () => {
    const opts = await getOptions()
    o_host          .value = opts.host
    o_token         .value = opts.token
    o_verbose_errors.value = opts.verbose_errors_on
    o_contexts_popup.value = opts.contexts_popup_on
    o_detect_urls   .value = opts.detect_sidebar_urls
    o_highlights_on .value = opts.highlight_on
    // todo getDots().checked    = opts.dots;

    const CodeMirror = await importCM()

    // TODO it should know the syntax? or infer from the class??
    for (const [el, value] of [
        [o_blacklist   , opts.blacklist   ],
        [o_filterlists , opts.filterlists ],
        [o_src_map     , opts.src_map     ],
        [o_position_css, opts.position_css],
        [o_extra_css   , opts.extra_css   ],
    ]) {
        el.bind({CodeMirror: CodeMirror})
        el.value = value
    }
}));

// TODO careful here if I ever implement not showing notifications?
// defensify might need to alert then...
unwrap(document.getElementById('save_id')).addEventListener('click', defensifyAlert(async () => {
    // todo make opts active object so we don't query unnecessary things like blacklist every time?
    const opts = {
        host               : o_host          .value,
        token              : o_token         .value,
        verbose_errors_on  : o_verbose_errors.value,
        contexts_popup_on  : o_contexts_popup.value,
        detect_sidebar_urls: o_detect_urls   .value,
        highlight_on       : o_highlights_on .value,
        dots          : true, // todo? getDots().checked,
        blacklist          : o_blacklist     .value,
        filterlists        : o_filterlists   .value,
        src_map            : o_src_map       .value,
        position_css       : o_position_css  .value,
        extra_css          : o_extra_css     .value,
    };
    await setOptions(opts);
    alert("Saved!");
}));


// https://stackoverflow.com/questions/46946380/fetch-api-request-timeout
// not fully correct, need to cancel request; but hopefully ok for now
function fetchTimeout(url, options, timeout) {
    return new Promise((resolve, reject) => {
        fetch(url, options).then(resolve, reject);

        if (timeout) {
            const e = new Error("Connection timed out");
            setTimeout(reject, timeout, e);
        }
    });
}

unwrap(document.getElementById('backend_status_id')).addEventListener('click', defensifyAlert(async() => {
    const host  = o_host .value
    const token = o_token.value

    const second = 1000;
    await fetchTimeout(`${host}/status`, {
        method: 'POST',
        headers: {
            'Authorization': "Basic " + btoa(token),
        },
    }, second).then(res => {
        if (!res.ok) {
            throw new Error(`Backend error: ${res.status} ${res.statusText}`)
        }
        return res;
    }).then(async res => {
        // TODO ugh. need to reject if ok is false...
        const resj = await res.json()
        alert(`Success! ${JSON.stringify(resj)}`)
    }, err => {
        alertError(`${err}. See https://github.com/karlicoss/promnesia/blob/master/doc/TROUBLESHOOTING.org`);
    });
}));
