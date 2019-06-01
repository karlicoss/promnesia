/* @flow */

type TagMap = {
    [string]: string
};

export type Options = {
    host: string;
    dots: boolean;
    token: string;
    blacklist: Array<string>;
    tag_map: TagMap;
}

// TODO how to export settings?? seriously need some standard package for settings
function default_options(): Options {
    return {
        host: "http://localhost:13131",
        dots: true,
        token: "",
        blacklist: [],
        tag_map: {},
    };
}

export function get_options(cb: (Options) => void)  {
    chrome.storage.local.get(null, res => {
        const optss = res.options || '{}';
        const saved_opts = JSON.parse(optss);
        const opts = {...default_options(), ...saved_opts};
        cb(opts);
    });
}

export function set_options(opts: Options, cb: () => void) {
    // ugh. making sure every field is a string is too annoying
    // just easier to store on big settings payload?
    // TODO can we even store array in local store???

    const optss = JSON.stringify(opts);
    console.log('Saving %s', optss);
    chrome.storage.local.set({'options': optss}, cb);
}
