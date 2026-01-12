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
    if (target === T.FIREFOX) { // only supported in firefox https://github.com/mozilla/web-ext/issues/2874
        // otherwise firefox hides the icon under the "puzzle piece" menu
        // At the very least it's annoying for testing, but also for promnesia it makes sense to show anyway
        action["default_area"] = "navbar"
        // in chrome, we're achieving the same thing by injecting "key" (see below)
    }


    const host_permissions = [
        // broad permissions (*) are necessary for webNavigation and scripting apis to work
        // otherwise we get "Cannot access contents of the page. Extension manifest must request permission to access the respective host."
        'file:///*',
        'http://*/*',
        'https://*/*',
        /* also note that if we have host permissions, we don't need tabs/activeTab permission to inject css/code
         * this is necessary to call insertCss and executeScript
         * note that just activeTab isn't enough because things aren't necessarily happening after user interaction like action
         * e.g. sidebar/icon state is updating after webNavigation callback
         */
    ]


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

        // needed to inject CSS/execute JS within pages
        // NOTE: needs to be paired with host permissions to allow injecting code/css into tabs
        "scripting",
    ]


    const optional_permissions = []

    const background = {}
    if (v3) {
        if (target === T.CHROME) {
            // webext lint will warn about this since it's not supported in firefox yet
            // see https://github.com/mozilla/web-ext/issues/2916
            background['service_worker'] = 'background.js'
        } else {
            background['scripts'] = ['background.js']
        }
    } else {
        background['scripts'] = ['background.js']
        background['persistent'] = false
    }
    background['type'] = 'module'

    const _resources = [
        "sidebar.css", // injected in the sidebar
        "*.js.map",    // debugging symbols
    ]

    const web_accessible_resources = v3 ? [{resources: _resources, matches: [ '*://*/*']}] : _resources
    const content_scripts = []

    // this is only needed during testing
    if (!publish) {
        // NOTE: ugh seems like in some browsers (firefox?) this may implicitly grant broad host permissions during installation??
        content_scripts.push({"matches": ["<all_urls>"], "js": ["selenium_bridge.js"]})
    }

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

    if (content_scripts.length > 0) {
        manifest['content_scripts'] = content_scripts
    }

    if (target === T.FIREFOX && v3) {
        // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy#upgrade_insecure_network_requests_in_manifest_v3
        // Firefox v3 manifest is trying to always force https, which isn't ideal for small backend like grasp (seemsingly unless it's localhost)
        // I.e. can see in devtools
        //   Content-Security-Policy: Upgrading insecure request ‘http://hostname:17890/capture’ to use ‘https’
        // , after that it fails to talk to the server via https, and it manifests as network error.

        // See https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy#default_content_security_policy
        // This is just default policy, but with 'upgrade-insecure-requests' excluded
        const content_security_policy = "script-src 'self'"

        manifest.content_security_policy = {extension_pages: content_security_policy}
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
    } else {
        manifest.permissions.push(...host_permissions)
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
    if (target === T.CHROME) {
        // to achieve stable extension id, needs "key" in manifest.json (this is injected in generate_manifest)
        // see https://developer.chrome.com/docs/extensions/reference/manifest/key
        manifest['key'] = "cHJvbW5lc2lhLWV4dGVuc2lvbi1pZA=="  // this needs to be a base64 string
    }
    return manifest
}
