/**
 * NOTE: I switched to rollup now, but keeping webpack config just for future reference
 */
const webpack = require('webpack'),
      path = require('path'),
      {CleanWebpackPlugin} = require('clean-webpack-plugin'),
      CopyWebpackPlugin = require('copy-webpack-plugin');

const T = {
    CHROME  : 'chrome',
    FIREFOX: 'firefox',
}


const env = {
    TARGET : process.env.TARGET,
    RELEASE: process.env.RELEASE,
    PUBLISH: process.env.PUBLISH,
    MANIFEST: process.env.MANIFEST,
}

// TODO will be conditional on T.CHROME at some point
const v3 = process.env.MANIFEST === '3'

const ext_id = process.env.EXT_ID

const pkg = require('./package.json');

const release = env.RELEASE == 'YES' ? true : false;
const publish = env.PUBLISH == 'YES' ? true : false;
const dev = !release; // meh. maybe make up my mind?
const target = env.TARGET; // TODO erm didn't work?? assert(target != null);

// see this for up to date info on the differences..
// https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Differences_between_desktop_and_Android#Other_UI_related_API_and_manifest.json_key_differences
// const isMobile = target.includes('mobile');

const name = 'Promnesia' + (dev ? ' [dev]' : '')


// ugh. declarative formats are shit.


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

commands[`_execute_${action_name}`] =  {
    "description": "Activate sidebar",
    "suggested_key": {
      /* fucking hell, ubuntu is hijacking Ctrl-Shift-E... not sure what to do :(
       * https://superuser.com/questions/358749/how-to-disable-ctrlshiftu-in-ubuntu-linux/1392682
       * */
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
    'http://'  + domain + '/',
    'https://' + domain + '/',
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
     * */
]
// FIXME not sure if need these considering it needs broad host permissions anyway?
const optional_host_permissions = endpoints('*')


// TODO make permissions literate
const permissions = [
    'storage',

    'webNavigation',
    'contextMenus',

    // todo could be optional?
    'notifications',

    // todo could be optional?
    'bookmarks',   // NOTE: isn't available on mobile

    // todo could be optional?
    'history',  // NOTE: isn't available on mobile
]


const optional_permissions = []


const content_security_policy = [
    "script-src 'self'",  // this must be specified when overriding, otherwise it complains
    /// also this works, but it seems that default-src somehow shadows style-src???
    // "default-src 'self'",
    // "style-src 'unsafe-inline'", // FFS, otherwise <style> directives on extension's pages not working??
    ///

    // also need to override it to exclude 'upgrade-insecure-requests' in manifest v3?
    // https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy#upgrade_insecure_network_requests_in_manifest_v3
    // NOTE: could be connect-src http: https: to allow all?
    // but we're specifically allowing endpoints that have /capture in them FIXME misleading mention of grasp?
    "connect-src " + endpoints('*:*').join(' '),
].join('; ')


const scripts = [
    'background.js',
    'webext-options-sync.js', // TODO need to get rid of this... so I can specify service_worker (it takes just one string)
]

const background = {}

if (v3) {
    if (target === T.CHROME) {
        // webext lint will warn about this since it's not supported in firefox yet
        background['service_worker'] = 'background.js'

        // this isn't supported in chrome manifest v3 (chrome warns about unsupported field)
        // but without it webext lint fails
        background['scripts'] = scripts

        // see header of background.js, this was for some experiments
        // NOTE: not working in firefox? just fails to load the manifest
        // background['type'] = 'module'
    } else {
      background['scripts'] = scripts
    }
} else {
  background['scripts'] = scripts
  background['persistent'] = false
}


const _resources = [
    "sidebar.css", // injected in the sidebar
    "*.js.map",    // debugging symbols
]

const web_accessible_resources = v3 ? [{resources: _resources, matches: [ '*://*/*']}] : _resources

const manifest = {
    name: name,
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

if (dev) {
    // TODO -- not sure what this was for??
    // manifest.content_security_policy = "script-src 'self' 'unsafe-eval'; object-src 'self'"
}


if (v3) {
    if (target === T.FIREFOX) {
        // firefox doesn't support optional host permissions
        // note that these will still have to be granted by user (unlike in chrome)
        manifest.host_permissions = [...host_permissions, ...optional_host_permissions]
    } else {
        manifest.host_permissions = host_permissions
        manifest.optional_host_permissions = optional_host_permissions
    }
} else {
    manifest.permissions.push(...host_permissions)
    manifest.optional_permissions.push(...optional_host_permissions)
}


// NOTE: this is only for mobile Firefox, we dynamically enable it in background page
// NOTE: chrome doesn't allow both page_action and browser_action in manifest
// https://stackoverflow.com/questions/7888915/why-i-cannot-use-two-or-more-browser-action-page-action-or-app-together
// for Firefox, it will also be deprecated in manifest v3 at some point? keeping for now just in case
// https://extensionworkshop.com/documentation/develop/manifest-v3-migration-guide/
if (target != T.CHROME) {
    manifest.page_action = {
        default_icon: {
            "48": "images/ic_visited_48.png"
        },
        default_title: "Promnesia",
    }
}


// FIXME should it be conditional on publishing??
if (v3 || target === T.FIREFOX) {
  // this isn't really required in chrome (it warns about unrecognised browser_specific_settings)
  // but without it, webext lint fails for chrome addon
  // if this isn't specified in firefox, it's complaining that storage api isn't available in background worker :shrug:
  const gecko_id = target === T.FIREFOX ? ext_id : "{00000000-0000-0000-0000-000000000000}"
  manifest.browser_specific_settings = {
      gecko: {
          id: gecko_id,
      },
  }
}

const buildPath = path.join(__dirname, 'dist', target)

const options = {
  mode: dev ? 'development' : 'production',
  node: {
    // no idea what does it mean... https://github.com/webpack/webpack/issues/5627#issuecomment-394290231
    // but it does get rid of some Function() which webpack generates (and which is flagged by web-ext lint)
    // this was still necessary at times (depending on webpack imports) circa 2023
    global: false,
  },
  entry: {
    background: {
      import: path.join(__dirname, './src/background.ts'),
      dependOn: ['webext-options-sync'],
    },
    options_page: {
      import: path.join(__dirname, './src/options_page.ts'),
      dependOn: ['webext-options-sync'],
    },
    sidebar: {
      import: path.join(__dirname, './src/sidebar.ts'),
      dependOn: ['webext-options-sync'],
    },
    search: {
      import: path.join(__dirname, './src/search.ts'),
      dependOn: ['webext-options-sync'],
    },
    'webext-options-sync': {
      import: "webext-options-sync",
    },
    anchorme: {
      import: 'anchorme',
      library: {
        name: 'promnesia_anchorme',
        type: "window", /* 'sets' library to window. variable... all the other types didn't work :( */
      },
    },
    showvisited: {
      import: path.join(__dirname, './src/showvisited'),
    },
  },
  output: {
    // hmm. according to https://stackoverflow.com/a/64715069
    // settings publicPath: '' shouldn't be necessary anymore
    // but still without it getting "Automatic publicPath is not supported in this browser" when trying to open sidebar
    // whatever.
    publicPath: '',
    path: buildPath,
    filename: '[name].js',
    // chunkFilename: '[name].bundle.js',
  },
  optimization: {
    // https://webpack.js.org/configuration/optimization
    minimize: !dev,
    splitChunks: {
      automaticNameDelimiter: '_', // ugh. default ~ can't be loaded by the browser??
    },
  },
  module: {
    // todo no idea why is exclude: /node_modules/ necessary here???
      rules: [
      {
          test: /\.js$/,
          loader: 'babel-loader',
          exclude: /node_modules/,
      },
      {
          test: /\.tsx?$/,
          use: 'ts-loader',
          exclude: /node_modules/,
      },
      {
          test: /\.css$/i,  // todo why case independent??
          use: ['style-loader', 'css-loader'],
          // hmm, if we add the exclude, codemirror.css loading isn't working???
          // exclude: /node_modules/,
      },
      {
          test: /\.html$/,
          loader: 'html-loader',
          exclude: /node_modules/
      },
    ]
  },
  resolve: {
      // this is necessary to import .ts files
      extensions: ['.tsx', '.ts', '.js'],
  },
  plugins: [
    new CleanWebpackPlugin(), // ok, respects symlinks

    // without copy plugin, webpack only bundles js/json files referenced in entrypoints
    new CopyWebpackPlugin({
      patterns: [
        { from: 'images/*.png' },
        { context: 'src', from: '**/*.html'     },
        { context: 'src', from: '**/*.css'      },
        // these js files aren't entrypoints so need copying too
        // not sure if it's the right way, but I guess webpack can't guess otherwise
        { context: 'src', from: 'toastify.js'   },  // TODO my version is tweaked, right?
        { context: 'src', from: 'selenium_bridge.js' },
        {
            // due to firefox + chrome and manifest v2 + v3 combination, 95% of the manifest is JS generated anyway
            // so with this we're just generaing it fully dynamically
            // in addition, WebpackExtensionManifestPlugin is outdated, hasn't been updated for a while
            from: 'webpack.config.js',
            to: path.join(buildPath, 'manifest.json'),
            transform: (content, path) => JSON.stringify(manifest, null, 2),
        },
       ]
    }),
  ],
  // docs claim it's the slowest but pretty fast anyway
  // also works with production builds
  devtool: 'source-map',
}


module.exports = options;
