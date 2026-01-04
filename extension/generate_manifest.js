// FIXME -- still need to sync more things with grasp
// mainly maybe consider dropping manifest v2...
// due to firefox + chrome and manifest v2 + v3 combination, 95% of the manifest is JS generated anyway
// so with this we're just generating it fully dynamically

import assert from 'assert'

import pkg from './package.json' with { type: "json" }

const T = {
    CHROME : 'chrome',
    FIREFOX: 'firefox',
}


// ugh. declarative formats are shit.
export function generateManifest({
    target,  // str
    manifest_version, // str
    publish, // bool
    ext_id   // str
} = {}) {
    assert(target)
    assert(manifest_version)
    assert(publish !== null)
    assert(ext_id)

    const v3 = manifest_version == '3'

    // Firefox wouldn't let you rebind its default shortcuts most of which use Shift
    // On the other hand, Chrome wouldn't let you use Alt
    const modifier = target === T.CHROME ? 'Shift' : 'Alt'

    const action_name = v3 ? 'action' : 'browser_action'

    const commands = {
        "mark_visited": {
            "description": "Mark/unmark visited links on the current page",
            "suggested_key": {
                "default": `Ctrl+${modifier}+V`,
                "mac":  `Command+${modifier}+V`,
            },
        },
        // right, 'S' interferes with OS hotkey?
        // need all of that discoverable from menu anyway
        // also dots and browser action too
        "search": {
            "description": "Open search page",
            "suggested_key": {
                "default": `Ctrl+${modifier}+H`,
                "mac":  `Command+${modifier}+H`,
            },
        },
    }

    commands[`_execute_${action_name}`] = {
        "description": "Activate sidebar",
        "suggested_key": {
            /* fucking hell, ubuntu is hijacking Ctrl-Shift-E... not sure what to do :(
             * https://superuser.com/questions/358749/how-to-disable-ctrlshiftu-in-ubuntu-linux/1392682
             */
            "default": `Ctrl+${modifier}+E`,
            "mac":  `Command+${modifier}+E`,
        },
    }


    const action = {
        "default_icon": "images/ic_not_visited_48.png",
        "default_title": "Show promnesia sidebar",
    }


    const endpoints = (domain) => [
        // TODO not sure if need to include api subpages?? seems like connect-src doesn't like /* in path component..
        "http://"  + domain + "/",
        "https://" + domain + "/",
    ]


    // prepare for manifest v3
    const host_permissions = [
        // broad permissions (*) are necessary for webNavigation to work
        // otherwise we get "Cannot access contents of the page. Extension manifest must request permission to access the respective host."
        'file:///*',
        ...endpoints('*'),
        /* also note that if we have host permissions, we don't need tabs/activeTab permission to inject css/code
         * this is necessary to call insertCss and executeScript
         * note that just activeTab isn't enough because things aren't necessarily happening after user interaction like action
         * e.g. sidebar/icon state is updating after webNavigation callback
         */
    ]
    // FIXME not sure if need these considering it needs broad host permissions anyway?
    const optional_host_permissions = endpoints('*')


    // TODO make permissions literate
    // keep in sync with readme
    const permissions = [
        // for keeping extension settings
        "storage",

        // receiving page status updates so extension kicks in on page loading
        "webNavigation",

        // uses context menu actions
        "contextMenus",

        // todo could be optional?
        "notifications",

        // used as one of the sources
        // todo could be optional?
        "bookmarks",   // NOTE: isn't available on mobile

        // to use local browsing history
        // todo could be optional?
        "history",  // NOTE: isn't available on mobile
    ]


    const optional_permissions = []

    if (target === T.FIREFOX || v3) {
        // chrome v2 doesn't support scripting api
        // FIXME need to actually start using it
        permissions.push("scripting")
    }


    const content_security_policy = [
        "script-src 'self'",  // this must be specified when overriding, otherwise it complains
        /// also this works, but it seems that default-src somehow shadows style-src???
        // "default-src 'self'",
        // "style-src 'unsafe-inline'", // FFS, otherwise <style> directives on extension's pages not working??
        ///

        // also need to override it to eclude 'upgrade-insecure-requests' in manifest v3?
        // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy#upgrade_insecure_network_requests_in_manifest_v3
        // NOTE: could be connect-src http: https: to allow all?
        // but we're specifically allowing endpoints that have /capture in them
        "connect-src " + endpoints('*:*').join(' '),
    ].join('; ')


    const background = {}
    if (v3) {
        if (target === T.CHROME) {
            // webext lint will warn about this since it's not supported in firefox yet
            // see https://github.com/mozilla/web-ext/issues/2916
            background['service_worker'] = 'background.js'

            // this isn't supported in chrome manifest v3 (chrome warns about unsupported field)
            // but NOT in older chrome versions (on which end2end tests are actually working)
            // -- if you specify scripts, loading extension actually fails
            // ... but without it webext lint fails
            // background['scripts'] = ['background.js']
            // sigh... ended up adding a wrapper around webext lint to filter out this one error for chrome...
        } else {
            background['scripts'] = ['background.js']
        }
    } else {
        if (target === T.CHROME) {
            background['scripts'] = ['background_chrome_mv2.js']
        } else {
            background['scripts'] = ['background.js']
        }
        background['persistent'] = false
    }
    // this doesn't have any effect in mv2 chrome, see the hack above for chrome specifically
    background['type'] = 'module'

    const _resources = [
        "sidebar.css", // injected in the sidebar
        "*.js.map",    // debugging symbols
    ]

    const web_accessible_resources = v3 ? [{resources: _resources, matches: [ '*://*/*']}] : _resources

    const manifest = {
        name: pkg.name + (publish ? '' : ' [dev]'),
        version: pkg.version,
        description: pkg.description,
        permissions: permissions,
        commands: commands,  // NOTE: this doesn't have any effect on mobile
        optional_permissions: optional_permissions,
        manifest_version: v3 ? 3 : 2,
        background: background,
        icons: {
            "48": "images/ic_not_visited_48.png",
        },
        options_ui: {
            page: 'options_page.html',
            open_in_tab: true,
        },
        web_accessible_resources: web_accessible_resources,
    }
    manifest[action_name] = action

    if (target === T.FIREFOX) {
        // NOTE: chrome v3 works without content_security_policy??
        // but in firefox it refuses to make a request even when we allow hostname permission??
        manifest.content_security_policy = (v3 ? {extension_pages: content_security_policy} : content_security_policy)
    }

    // this is only needed during testing
    if (!publish) {
        manifest.content_scripts = [{"matches": ["<all_urls>"], "js": ["selenium_bridge.js"]}]
    }

    // NOTE: this is only for mobile Firefox, we dynamically enable it in background page
    // NOTE: chrome doesn't allow both page_action and browser_action in manifest
    // https://stackoverflow.com/questions/7888915/why-i-cannot-use-two-or-more-browser-action-page-action-or-app-together
    // for Firefox, it will also be deprecated in manifest v3 at some point? keeping for now just in case
    // https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/
    if (target !== T.CHROME) {
        manifest.page_action = {
            default_icon: {
                "48": "images/ic_visited_48.png"
            },
            default_title: "Promnesia",
        }
    }

    if (v3) {
        manifest.host_permissions = host_permissions
        manifest.optional_host_permissions = optional_host_permissions
    } else {
        manifest.permissions.push(...host_permissions)
        manifest.optional_permissions.push(...optional_host_permissions)
    }

    if (target === T.FIREFOX || v3) {
        // for firefox, this is required during publishing?
        // this isn't really required in chrome, but without it, webext lint fails for chrome addon
        const gecko_id = target === T.FIREFOX ? ext_id : '{00000000-0000-0000-0000-000000000000}'
        manifest['browser_specific_settings'] = {
            'gecko': {
                'id': gecko_id,
                'data_collection_permissions': {  // required for new firefox addons
                    'required': ['none']
                },
            },
        }
    }
    return manifest
}
