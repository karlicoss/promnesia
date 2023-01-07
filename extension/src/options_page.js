/* @flow */
import {unwrap} from './common'
import {getStoredOptions, setOptions, resetOptions} from './options'
import {defensifyAlert, alertError} from './notifications'


class Option<T> {
    id: string

    constructor(id: string) {
        this.id = id
    }

    async setValue(_: T): Promise<void> {
        throw new Error("AAA")
    }

    async getValue(): Promise<T> {
        throw new Error("AAA")
    }

    get element(): HTMLInputElement {
        return ((document.getElementById(this.id): any): HTMLInputElement);
    }
}

class Simple extends Option<string> {
    async setValue(x: string): Promise<void> {
        this.element.value = x
    }

    async getValue(): Promise<string> {
        return this.element.value
    }
}

class ONumber extends Option<number> {
    async setValue(x: number): Promise<void> {
        this.element.value = String(x)
    }
    async getValue(): Promise<number> {
        return parseInt(this.element.value)
    }
}

class Toggle extends Option<boolean> {
    async setValue(x: boolean): Promise<void> {
        this.element.checked = x
    }

    async getValue(): Promise<boolean> {
        return this.element.checked
    }
}

// none means 'rely on the default set by developer'
class IToggle extends Option<?boolean> {
    async setValue(x: ?boolean): Promise<void> {
        if (x == null) {
            this.element.indeterminate = true
        } else {
            this.element.checked = x
        }
    }

    async getValue(): Promise<?boolean> {
        if (this.element.indeterminate) {
            return null
        } else {
            return this.element.checked
        }
    }
}

class Editor extends Option<string> {
    mode: ?string
    constructor(id: string, {mode}: {mode: ?string}) {
        super(id)
        this.mode = mode
    }

    async setValue(x: string): Promise<void> {
        const editor = await this.editor()
        editor.dispatch({
            changes: {from: 0, to: editor.state.doc.length, insert: x}
        })
    }

    async getValue(): Promise<string> {
        return (await this.editor()).state.doc.toString()
    }

    // $FlowFixMe[missing-local-annot]
    async bind(value: string): Promise<void> {
        // $FlowFixMe[cannot-resolve-module]
        const {EditorView, minimalSetup} = await import(/* webpackChunkName: "codermirror" */"codemirror")
        // $FlowFixMe[cannot-resolve-module]
        const {highlightActiveLine, lineNumbers, highlightActiveLineGutter} = await import (/* webpackChunkName: "codermirror" */"@codemirror/view")
        // $FlowFixMe[cannot-resolve-module]
        const {indentOnInput, bracketMatching} = await import (/* webpackChunkName: "codermirror" */"@codemirror/language")
        // $FlowFixMe[cannot-resolve-module]
        const {highlightSelectionMatches} = await import (/* webpackChunkName: "codermirror" */"@codemirror/search")
        // $FlowFixMe[cannot-resolve-module]
        const {autocompletion} = await import (/* webpackChunkName: "codermirror" */"@codemirror/autocomplete")
        // $FlowFixMe[cannot-resolve-module]
        const {Compartment} = await import (/* webpackChunkName: "codermirror" */"@codemirror/state")
        // $FlowFixMe[cannot-resolve-module]
        const {css} = await import (/* webpackChunkName: "codermirror" */"@codemirror/lang-css")
        // $FlowFixMe[cannot-resolve-module]
        const {javascript} = await import (/* webpackChunkName: "codermirror" */"@codemirror/lang-javascript")

        // see https://github.com/codemirror/basic-setup/blob/main/src/codemirror.ts
        // and https://codemirror.net/docs/ref/
        const extra_extensions = [
            lineNumbers(),
            highlightActiveLineGutter(),
            indentOnInput(),
            bracketMatching(),
            autocompletion(),  // TODO not sure..
            highlightActiveLine(),
            highlightSelectionMatches(),
        ]
        let language = new Compartment
        const lang = []
        if (this.mode === 'javascript') {
            lang.push(language.of(javascript()))
        } else if (this.mode == 'css') {
            lang.push(language.of(css()))
        }

        new EditorView({
            extensions: [
                minimalSetup,
                ...lang,
                ...extra_extensions,
            ],
            parent: this.element,
            doc: value,
        })
    }

    // $FlowFixMe[missing-local-annot]
    async editor() {
        // $FlowFixMe[cannot-resolve-module]
        const {EditorView} = await import(/* webpackChunkName: "codermirror" */"codemirror")
        return unwrap(EditorView.findFromDOM(this.element))
    }
}
// end

const o_host           = new Simple('host_id'               )
const o_token          = new Simple('token_id'              )
const o_use_bookmarks      = new Toggle('use_bookmarks_id'     )
const o_use_browserhistory = new Toggle('use_browserhistory_id')
const o_browserhistory_max_results = new ONumber('browserhistory_max_results_id')
const o_verbose_errors = new Toggle('verbose_errors_id'     )
const o_contexts_popup = new Toggle('contexts_popup_id'     )
const o_sidebar_detect_urls = new Toggle('sidebar_detect_urls_id')
const o_sidebar_always_show = new IToggle('sidebar_always_show_id')
const o_highlights_on  = new Toggle('highlight_id'          )
const o_mark_visited_always = new IToggle('mark_visited_always_id')

const o_mark_visited_excludelist = new Editor('mark_visited_excludelist_id', {mode: null        })
const o_global_excludelist       = new Editor('global_excludelist_id'      , {mode: null        })
const o_global_excludelists_ext  = new Editor('global_excludelists_ext_id' , {mode: 'javascript'})
const o_src_map      = new Editor('source_map_id'  , {mode: 'javascript'})
const o_position_css = new Editor('position_css_id', {mode: 'css' })
const o_extra_css    = new Editor('extra_css_id'   , {mode: 'css' })


document.addEventListener('DOMContentLoaded', defensifyAlert(async () => {
    const opts = await getStoredOptions()
    await o_host                      .setValue(opts.host)
    await o_token                     .setValue(opts.token)
    await o_use_bookmarks             .setValue(opts.use_bookmarks)
    await o_use_browserhistory        .setValue(opts.use_browserhistory)
    await o_browserhistory_max_results.setValue(opts.browserhistory_max_results)
    await o_verbose_errors            .setValue(opts.verbose_errors_on)
    await o_contexts_popup            .setValue(opts.contexts_popup_on)
    await o_sidebar_detect_urls       .setValue(opts.sidebar_detect_urls)
    await o_sidebar_always_show       .setValue(opts.sidebar_always_show)
    await o_highlights_on             .setValue(opts.highlight_on)
    await o_mark_visited_always       .setValue(opts.mark_visited_always)

    // TODO it should know the syntax? or infer from the class??
    for (const [el, value] of [
        [o_mark_visited_excludelist, opts.mark_visited_excludelist],
        [o_global_excludelist      , opts.blacklist               ],
        [o_global_excludelists_ext , opts.global_excludelists_ext ],
        [o_src_map                 , opts.src_map                 ],
        [o_position_css            , opts.position_css            ],
        [o_extra_css               , opts.extra_css               ],
    ]) {
        await el.bind(value)
    }

    /* a marker for tests */
    const settings_loaded = document.createElement('span')
    settings_loaded.id = 'promnesia-settings-loaded'
    settings_loaded.style.display = 'none'

    unwrap(document.body).appendChild(settings_loaded)
}));


// https://stackoverflow.com/a/34156339/706389
function download(content: string, fileName: string, contentType: string) {
    var a = document.createElement("a")
    var file = new Blob([content], {type: contentType})
    a.href = URL.createObjectURL(file)
    a.download = fileName
    a.click()
}

unwrap(document.getElementById(
    'export_settings_id'
)).addEventListener('click', defensifyAlert(async () => {
    // NOTE: gets all keys, including the old onces, just what we need
    const opts = await getStoredOptions()
    download(JSON.stringify(opts), 'promnesia_settings.json', 'text/json')
}))

// TODO careful here if I ever implement not showing notifications?
// defensify might need to alert then...
unwrap(document.getElementById(
    'save_id'
)).addEventListener('click', defensifyAlert(async () => {
    // todo make opts active object so we don't query unnecessary things like blacklist every time?
    const opts = {
        host                      : await (o_host                      .getValue()),
        token                     : await (o_token                     .getValue()),
        use_bookmarks             : await (o_use_bookmarks             .getValue()),
        use_browserhistory        : await (o_use_browserhistory        .getValue()),
        browserhistory_max_results: await (o_browserhistory_max_results.getValue()),
        verbose_errors_on         : await (o_verbose_errors            .getValue()),
        contexts_popup_on         : await (o_contexts_popup            .getValue()),
        sidebar_detect_urls       : await (o_sidebar_detect_urls       .getValue()),
        sidebar_always_show       : await (o_sidebar_always_show       .getValue()),
        highlight_on              : await (o_highlights_on             .getValue()),
        mark_visited_always       : await (o_mark_visited_always       .getValue()),
        mark_visited_excludelist  : await (o_mark_visited_excludelist  .getValue()),
        blacklist                 : await (o_global_excludelist        .getValue()),
        global_excludelists_ext   : await (o_global_excludelists_ext   .getValue()),
        src_map                   : await (o_src_map                   .getValue()),
        position_css              : await (o_position_css              .getValue()),
        extra_css                 : await (o_extra_css                 .getValue()),
    };
    await setOptions(opts);
    alert("Saved!");
}));

unwrap(document.getElementById(
    'reset_id',
)).addEventListener('click', defensifyAlert(async() => {
    if (confirm('This will RESET your settings! Make sure you exported them first.')) {
        await resetOptions()
        alert('Reset! Reload the page to see the effect.')
    }
}))


// https://stackoverflow.com/questions/46946380/fetch-api-request-timeout
// not fully correct, need to cancel request; but hopefully ok for now
function fetchTimeout(url: string, options: any, timeout: ?number): Promise<any> {
    return new Promise((resolve, reject) => {
        fetch(url, options).then(resolve, reject);

        if (timeout) {
            const e = new Error("Connection timed out");
            setTimeout(reject, timeout, e);
        }
    });
}

unwrap(document.getElementById('backend_status_id')).addEventListener('click', defensifyAlert(async() => {
    const host  = await o_host .getValue()
    const token = await o_token.getValue()

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
