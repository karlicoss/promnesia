const path = require('path'),
      webpack = require('webpack'),
      CopyWebpackPlugin = require('copy-webpack-plugin'),
      CleanWebpackPlugin = require("clean-webpack-plugin"),
      WebpackExtensionManifestPlugin = require('webpack-extension-manifest-plugin');

const env = {
    TARGET : process.env.TARGET,
    RELEASE: process.env.RELEASE,
};

const pkg = require('./package.json');
const baseManifest = require('./src/manifest.json');

const target = env.TARGET; // TODO erm didn't work?? assert(target != null);
const release = env.RELEASE == 'YES' ? true : false;


// Firefox wouldn't let you rebind its default shortcuts most of which use Shift
// On the other hand, Chrome wouldn't let you use Alt
const modifier = target === 'chrome' ? 'Shift' : 'Alt';

// ugh. declarative formats are shit.
const commandsExtra = {
    "_execute_browser_action": {
        "description": "Activate extension",
        "suggested_key": {
            "default": `Ctrl+${modifier}+E`,
            "mac":  `Command+${modifier}+E`
        }
    },
    "show_dots": {
        "description": "Activate dots for visited urls",
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


// see this for up to date info on the differences..
// https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Differences_between_desktop_and_Android#Other_UI_related_API_and_manifest.json_key_differences
const isMobile = target.includes('mobile');

// TODO ugh it's getting messy...
const action = {
    "default_icon": "images/ic_not_visited_48.png",
    "default_title": "Was not visited",
};


// TODO not sure why it is here?
if (isMobile) {
    action["default_popup"] = "popup.html";
    // TODO ok, need to refine and add things on that page...
    // TODO maybe show visits as on sidebar?
}

const permissionsExtra = [];

if (!isMobile) {
    permissionsExtra.push(
        'contextMenus',
        'history',
    );
}

const manifestExtra = {
    version: pkg.version,
    name: release ? "Promnesia" : "Promnesia (dev)",
    browser_action: action,
    permissions: permissionsExtra,
};

if (!isMobile) {
    manifestExtra.commands = commandsExtra;
}

if (isMobile) {
    // on mobile firefox pageAction makes a bit of sense due to various limitations...
    manifestExtra.pageAction = {
        browser_style: true,
        default_icon: {
            "48": "images/ic_visited_48.png"
        },
        default_title: "Promnesia",
    };
}


if (target === 'chrome') {
    manifestExtra.options_ui = {chrome_style: true};
} else if (target.includes('firefox')) {
    // TODO not sure if should do anything special for mobile
    manifestExtra.options_ui = {browser_style: true};
    manifestExtra.browser_action = {browser_style: true};
} else {
    throw new Error("unknown target " + target);
}

if (target.includes('firefox')) {
    manifestExtra.browser_specific_settings = {
        "gecko": {
            "id": "promnesia@karlicoss.github.com"
        }
    };
}



const buildPath = path.join(__dirname, 'dist', target);

const options = {
  mode: 'development',

  entry: {
    background   : path.join(__dirname, './src/background'),
    options_page : path.join(__dirname, './src/options_page'),
      // TODO remove popup?
    popup        : path.join(__dirname, './src/popup'),
    sidebar      : path.join(__dirname, './src/sidebar'),
    search       : path.join(__dirname, './src/search'),
    background_injector : path.join(__dirname, './src/background_injector'),
  },
  output: {
    path: buildPath,
    filename: '[name].js',
  },
  module: {
      rules: [{
          test: /\.js$/,
          exclude: /node_modules/,
          use: {
              loader: 'babel-loader',
          }
      },
      {
          test: /\.css$/i,
          use: ['style-loader', 'css-loader'],
      },
      {
          test: /\.html$/,
          loader: "html-loader",
          exclude: /node_modules/
      }
    ]
  },
  plugins: [
   new CleanWebpackPlugin([buildPath + "/*"]),
   new CopyWebpackPlugin([
      { from: 'images/*' },
      { from: 'shallalist/finance/banking/domains', to: 'shallalist/finance/banking' },
       // TODO webmail as well?
      { from: 'src/*.html' , flatten: true},
      { from: 'src/*.css' , flatten: true},
      { from: 'src/toastify.js', flatten: true},
    ]),
    new WebpackExtensionManifestPlugin({
        config: {
            base: baseManifest,
            extend: manifestExtra,
        }
    }),
  ]
};


module.exports = options;
