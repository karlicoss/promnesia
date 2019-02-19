/* @flow */

export type Options = {
    host: string;
    dots: boolean;
    token: string;
    blacklist: Array<string>;
}

function default_options(): Options {
    return {
        host: "http://localhost:13131",
        dots: true,
        token: "",
        blacklist: [],
    };
}

export function get_options(cb: (Options) => void)  {
    chrome.storage.local.get(null, res => {
        res = {...default_options(), ...res};
        cb(res);
    });
}

export function set_options(opts: Options, cb: () => void) {
    console.log('Saving %s', JSON.stringify(opts));
    chrome.storage.local.set(opts, cb);
}
