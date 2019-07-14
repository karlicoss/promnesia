/* @flow */

type Tag = string;

type TagMap = {
    [Tag]: Tag
};

export type Options = {
    host: string;
    dots: boolean;
    token: string;
    blacklist: Array<string>;
    tag_map: TagMap;
    extra_css: string;
}

// TODO how to export settings?? seriously need some standard package for settings
function default_options(): Options {
    return {
        host: "http://localhost:13131",
        dots: true,
        token: "",
        blacklist: [],
        tag_map: {},
        extra_css: "",
    };
}

export function get_options(cb: (Options) => void)  {
    // TODO make it as minimal as possible; rest should be async
    chrome.storage.local.get(null, res => {
        const optss = res.options || '{}';
        const saved_opts = JSON.parse(optss);
        const opts = {...default_options(), ...saved_opts};
        cb(opts);
    });
}


function create_promise<T>(provider: ((T) => void) => void): Promise<T> {
    return new Promise((resolve, reject) => {
        try {
            provider(resolve);
        } catch (err) {
            reject(err);
        }
    });
}

// TODO later rename to just get_options
export async function get_options_async(): Promise<Options> {
    return await create_promise(get_options);
}

export function set_options(opts: Options, cb: () => void) {
    // ugh. making sure every field is a string is too annoying
    // just easier to store on big settings payload?
    // TODO can we even store array in local store???

    const optss = JSON.stringify(opts);
    console.log('Saving %s', optss);
    chrome.storage.local.set({'options': optss}, cb);
}

export async function set_options_async(opts: Options) {
    return await create_promise(cb => set_options(opts, cb));
}
