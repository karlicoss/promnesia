/* @flow */
import {unwrap} from './common';
import {get_options_async, setOptions} from './options';
import {defensifyAlert, alertError} from './notifications';

// re: codemirror imports
// err. that's a bit stupid, js injected css? surely it can be done via webpack and static files...
// TODO right, I suppose that's why I need style bunder?
// turned out more tedious than expected... https://github.com/codemirror/CodeMirror/issues/5484#issue-338185331

function getInputElement(element_id: string): HTMLInputElement {
    return ((document.getElementById(element_id): any): HTMLInputElement);
}

function getElement(element_id: string): HTMLElement {
    return ((document.getElementById(element_id): any): HTMLElement);
}

function getHost(): HTMLInputElement {
    return getInputElement('host_id');
}

function getToken(): HTMLInputElement {
    return getInputElement('token_id');
}

function getVerboseErrorsOn(): HTMLInputElement {
    return getInputElement('verbose_errors_id');
}

function getHighlightOn(): HTMLInputElement {
    return getInputElement('highlight_id');
}

function getContextsPopupOn(): HTMLInputElement {
    return getInputElement('contexts_popup_id');
}

// function getDots(): HTMLInputElement {
//     return getInputElement('dots_id');
// }

function getBlackList(): HTMLInputElement {
    return getInputElement('blacklist_id');
}

function getSrcMap(): HTMLElement {
    return getElement('source_map_id');
}

function getPositionCss(): HTMLElement {
    return getElement('position_css_id');
}

function getExtraCss(): HTMLElement {
    return getElement('extra_css_id');
}

// TODO display it floating


function getEditor(el: HTMLElement) {
    // $FlowFixMe
    return el.querySelector('.CodeMirror').CodeMirror;
}


document.addEventListener('DOMContentLoaded', defensifyAlert(async () => {
    const opts = await get_options_async();
    getHost().value      = opts.host;
    getToken().value     = opts.token;

    getVerboseErrorsOn().checked = opts.verbose_errors_on;
    getContextsPopupOn().checked = opts.contexts_popup_on;

    getHighlightOn().checked = opts.highlight_on;

    // TODO I don't really understand, what's up with these fucking chunks and their naming
    // at least it reduces size of the options page

    const CM = await import(
        /* webpackChunkName: "codemirror-main" */
        // $FlowFixMe
        'codemirror/lib/codemirror.js'
    );
    const CodeMirror = CM.default; // ???

    // TODO just copy css in webpack directly??
    await import(
        /* webpackChunkName: "codemirror.css" */
        // $FlowFixMe
        'codemirror/lib/codemirror.css'
    );

    await import(
        /* webpackChunkName: "codemirror-css-module" */
        // $FlowFixMe
        'codemirror/mode/css/css.js'
    );

    await import(
        /* webpackChunkName: "codemirror-js-module" */
        // $FlowFixMe
        'codemirror/mode/javascript/javascript.js'
    );

    // getDots().checked    = opts.dots;
    CodeMirror(getBlackList(), {
        lineNumbers: true,
        value      : opts.blacklist,
    });

    // TODO tag map could be json?
    CodeMirror(getSrcMap(), {
        mode       : 'javascript',
        lineNumbers: true,
        value      : JSON.stringify(opts.src_map),
    });

    CodeMirror(getPositionCss(), {
        mode       : 'css',
        lineNumbers: true,
        value      : opts.position_css,
    });

    CodeMirror(getExtraCss(), {
        mode       :  'css',
        lineNumbers: true,
        value      : opts.extra_css,
    });
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
    const host = getHost().value;
    const token = getToken().value;

    const second = 1000;
    await fetchTimeout(`${host}/status`, {
        method: 'POST',
        headers: {
            'Authorization': "Basic " + btoa(token),
        },
    }, second).then(res => {
        if (!res.ok) {
            throw `Backend error: ${res.status} ${res.statusText}` // TODO
        }
        return res;
    }).then(async res => {
        // TODO ugh. need to reject if ok is false...
        const resj = await res.json()
        // TODO log debug?
        alert(`Success! ${JSON.stringify(resj)}`)
    }, err => {
        alertError(err);
    });
}));

// TODO careful here if I ever implement not showing notifications?
// defensify might need to alert then...
unwrap(document.getElementById('save_id')).addEventListener('click', defensifyAlert(async () => {
    // TODO make opts active object so we don't query unnecessary things like blacklist every time?
    const opts = {
        host      : getHost().value,
        token     : getToken().value,

        verbose_errors_on: getVerboseErrorsOn().checked,
        contexts_popup_on: getContextsPopupOn().checked,

        highlight_on: getHighlightOn().checked,

        dots      : true, // TODO? getDots().checked,
        blacklist : getEditor(getBlackList()).getValue(),

        src_map   : JSON.parse(getEditor(getSrcMap()).getValue()),
        position_css : getEditor(getPositionCss()).getValue(),
        extra_css    : getEditor(getExtraCss()).getValue(),
    };
    await setOptions(opts);
    alert("Saved!");
}));
