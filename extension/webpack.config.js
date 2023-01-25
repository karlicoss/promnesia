const webpack = require('webpack'),
      path = require('path'),
      {CleanWebpackPlugin} = require('clean-webpack-plugin'),
      CopyWebpackPlugin = require('copy-webpack-plugin'),
      WebpackExtensionManifestPlugin = require('webpack-extension-manifest-plugin');

const T = {
    CHROME  : 'chrome',
    FIREFOX: 'firefox',
};

const env = {
    TARGET : process.env.TARGET,
    RELEASE: process.env.RELEASE,
    PUBLISH: process.env.PUBLISH,
}
const ext_id = process.env.EXT_ID

const pkg = require('./package.json');
const baseManifest = require('./src/manifest.json');

const release = env.RELEASE == 'YES' ? true : false;
const publish = env.PUBLISH == 'YES' ? true : false;
const dev = !release; // meh. maybe make up my mind?
const target = env.TARGET; // TODO erm didn't work?? assert(target != null);

// see this for up to date info on the differences..
// https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Differences_between_desktop_and_Android#Other_UI_related_API_and_manifest.json_key_differences
// const isMobile = target.includes('mobile');

const name = 'Promnesia' + (dev ? ' [dev]' : '');

// Firefox wouldn't let you rebind its default shortcuts most of which use Shift
// On the other hand, Chrome wouldn't let you use Alt
const modifier = target === T.CHROME ? 'Shift' : 'Alt';

// ugh. declarative formats are shit.
const commandsExtra = {
    "_execute_browser_action": {
        "description": "Activate sidebar",
        "suggested_key": {
          /* fucking hell, ubuntu is hijacking Ctrl-Shift-E... not sure what to do :(
           * https://superuser.com/questions/358749/how-to-disable-ctrlshiftu-in-ubuntu-linux/1392682
           * */
            "default": `Ctrl+${modifier}+E`,
            "mac":  `Command+${modifier}+E`
        }
    },
    "mark_visited": {
        "description": "Mark/unmark visited links on the current page",
        "suggested_key": {
            "default": `Ctrl+${modifier}+V`,
            "mac":  `Command+${modifier}+V`
        }
    },
    // right, 'S' interferes with OS hotkey?
    // need all of that discoverable from menu anyway
    // also dots and browser action too
    "search": {
        "description": "Open search page",
        "suggested_key": {
            "default": `Ctrl+${modifier}+H`,
            "mac":  `Command+${modifier}+H`
        }
    }
};


// TODO ugh it's getting messy...
const action = {
    "default_icon": "images/ic_not_visited_48.png",
    "default_title": "Show promnesia sidebar",
};


const hostPermissions = [
  // these are necessary for webNavigation to work
  // otherwise we get "Cannot access contents of the page. Extension manifest must request permission to access the respective host."
  "file:///*",
  "https://*/*",
  "http://*/*",

  /* also note that if we have host permissions, we don't need tabs/activeTab permission to inject css/code
   * this is necessary to call insertCss and executeScript
   * note that just activeTab isn't enough because things aren't necessarily happening after user interaction like action
   * e.g. sidebar/icon state is updating after webNavigation callback
   * */
]

const permissions = [
  ...hostPermissions,

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


const manifestExtra = {
    name: name,
    version: pkg.version,
    description: "Indicates whether and when the page was visited (and more!)",
    icons: {
        "48": "images/ic_not_visited_48.png",
    },
    browser_action: action,
    permissions: permissions,
    options_ui: {},
    web_accessible_resources: [
        "sidebar.css", /* injected in the sidebar */
    ],
}

// this is only needed during testing
if (!publish) {
  manifestExtra.content_scripts = [
    {
      "matches": ["<all_urls>"],
      "js": ["selenium_bridge.js"],
    },
  ]
}

if (dev) {
    manifestExtra.content_security_policy = "script-src 'self' 'unsafe-eval'; object-src 'self'";
}

// NOTE: this doesn't have any effect on mobile
manifestExtra.commands = commandsExtra;

/*
 * TODO ??? from the debugger
 * Reading manifest: Error processing browser_action.browser_style: Unsupported on Android.
 * Warning details
 * Reading manifest: Error processing browser_action.default_icon:
 */

// TODO shit, how to validate manifest?? didn't find anything...

// NOTE: this is only for mobile Firefox, we dynamically enable it in background.js
// NOTE: chrome doesn't allow both page_action and browser_action in manifest
// https://stackoverflow.com/questions/7888915/why-i-cannot-use-two-or-more-browser-action-page-action-or-app-together
if (target != T.CHROME) {
    manifestExtra.page_action = {
        browser_style: true,
        default_icon: {
            "48": "images/ic_visited_48.png"
        },
        default_title: "Promnesia",
    };
}


if (target === T.CHROME) {
    manifestExtra.options_ui.chrome_style = true;
} else if (target.includes('firefox')) {
    // TODO not sure if should do anything special for mobile
    manifestExtra.options_ui.browser_style = true;
    manifestExtra.browser_action.browser_style = true;
} else {
    throw new Error("unknown target " + target);
}

// on mobile it looks kinda small-ish... but I think can be fixed with responsive CSS, fine.
manifestExtra.options_ui.open_in_tab = true;


if (!publish && target === T.FIREFOX) {
    /*
     * When we publish, the id used is AMO/CWS and provided by the build script
     * Otherwise, use temporary id (or some APIs don't work, at least in firefox..)
     */
    manifestExtra.browser_specific_settings = {
      gecko: {
        id: ext_id,
      },
    }
}


const buildPath = path.join(__dirname, 'dist', target);

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
      import: path.join(__dirname, './src/background'),
      dependOn: ['webext-options-sync'],
    },
    options_page: {
      import: path.join(__dirname, './src/options_page'),
      dependOn: ['webext-options-sync'],
    },
    sidebar: {
      import: path.join(__dirname, './src/sidebar'),
      dependOn: ['webext-options-sync'],
    },
    search: {
      import: path.join(__dirname, './src/search'),
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
        { context: 'src', from: 'showvisited.js'},
        { context: 'src', from: 'selenium_bridge.js' },
        { from: 'node_modules/webextension-polyfill/dist/browser-polyfill.js' },
       ]
    }),
    new WebpackExtensionManifestPlugin({
      config: {
        base: baseManifest,
        extend: manifestExtra,
      }
    }),
  ],
  // docs claim it's the slowest but pretty fast anyway
  // also works with production builds
  devtool: 'source-map',
}


module.exports = options;
