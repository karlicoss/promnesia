/* @flow */
import {unwrap} from './common';
import {get_options_async, setOptions} from './options';
import {defensifyAlert, alertError} from './notifications';

// $FlowFixMe
import reqwest from 'reqwest';

// $FlowFixMe
import CodeMirror from 'codemirror/lib/codemirror.js';
// $FlowFixMe
import 'codemirror/mode/css/css.js';
// err. that's a bit stupid, js injected css? surely it can be done via webpacke and static files...
// $FlowFixMe
import 'codemirror/lib/codemirror.css';
// turned out more tedious than expected... https://github.com/codemirror/CodeMirror/issues/5484#issue-338185331


function getInputElement(element_id: string): HTMLInputElement {
    return ((document.getElementById(element_id): any): HTMLInputElement);
}

function getHost(): HTMLInputElement {
    return getInputElement('host_id');
}

function getToken(): HTMLInputElement {
    return getInputElement('token_id');
}

function getDots(): HTMLInputElement {
    return getInputElement('dots_id');
}

function getBlackList(): HTMLInputElement {
    return getInputElement('blacklist_id');
}

function getTagMap(): HTMLInputElement {
    return getInputElement('tag_map_id');
}

function getWidth(): HTMLInputElement {
    return getInputElement('width_id');
}

function getExtraCss(): HTMLInputElement {
    return getInputElement('extra_css_id');
}

// TODO display it floating

function getCssEditor() {
    // $FlowFixMe
    return document.querySelector('.CodeMirror').CodeMirror;
}

document.addEventListener('DOMContentLoaded', defensifyAlert(async () => {
    const opts = await get_options_async();
    getHost().value      = opts.host;
    getToken().value     = opts.token;

    getDots().checked    = opts.dots;
    getBlackList().value = opts.blacklist.join('\n');
    // TODO tag map could be json?
    getTagMap().value    = JSON.stringify(opts.tag_map);

    getWidth().value     = opts.sidebar_width;
    getExtraCss().value  = opts.extra_css;

    CodeMirror.fromTextArea(getExtraCss(), {
        mode:  'css',
        lineNumbers: true,
    });
}));

unwrap(document.getElementById('backend_status_id')).addEventListener('click', defensifyAlert(async() => {
    const host = getHost().value;
    const token = getToken().value;

    await reqwest({
        url: `${host}/status`,
        method: 'post',
        headers: {
            'Authorization': "Basic " + btoa(token),
        },
        timeout: 1000, // 1s
    }).then(res => {
        console.log(res);
        alert(`Success! ${JSON.stringify(res)}`);
    }, err => {
        // TODO ugh. unclear how to transform error object, nothing seemed to work.
        // that results in two error alerts, but I guess thats' not so bad..
        alertError(`${err.status} ${err.statusText} ${err.response}`);
    });
}));

// TODO careful here if I ever implement not showing notifications?
// defensify might need to alert then...
unwrap(document.getElementById('save_id')).addEventListener('click', defensifyAlert(async () => {
    const opts = {
        host      : getHost().value,
        token     : getToken().value,

        dots      : getDots().checked,
        // this is preserving whitespaces so might end up with '' entries
        // but perhaps it's ok; lets the user space out blacklist entries
        // TODO also make sure we don't reorder entries in settings without user's permissions
        // I guess the real solution is blacklist object which keeps textual repr separately
        blacklist : getBlackList().value.split(/\n/),
        tag_map   : JSON.parse(getTagMap().value),

        sidebar_width: getWidth().value,
        extra_css : getCssEditor().getValue(),
    };
    await setOptions(opts);
    alert("Saved!");
}));
