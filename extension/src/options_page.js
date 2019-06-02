import {get_options, set_options} from './options';

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

function getExtraCss(): HTMLInputElement {
    return getInputElement('extra_css_id');
}

// TODO display it floating

document.addEventListener('DOMContentLoaded', () => {
    get_options(opts => {
        getHost().value      = opts.host;
        getDots().checked    = opts.dots;
        getToken().value     = opts.token;
        getBlackList().value = opts.blacklist.join('\n');
        getTagMap().value    = JSON.stringify(opts.tag_map);
        getExtraCss().value  = opts.extra_css;
    });
});
document.getElementById('save_id').addEventListener('click', () => {
    const opts = {
        host      : getHost().value,
        dots      : getDots().checked,
        token     : getToken().value,
        blacklist : getBlackList().value.split(/\n/),
        tag_map   : JSON.parse(getTagMap().value),
        extra_css : getExtraCss().value,
    };
    set_options(opts, () => { alert("Saved!"); });
});
