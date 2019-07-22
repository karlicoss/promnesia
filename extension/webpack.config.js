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
        "suggested_key": {
            "default": `Ctrl+${modifier}+W`,
            "mac":  `Command+${modifier}+W`
        }
    },
    "show_dots": {
        "suggested_key": {
            "default": `Ctrl+${modifier}+V`,
            "mac":  `Command+${modifier}+V`
        }
    },
    // right, 'S' interferes with OS hotkey?
    // need all of that discoverable from menu anyway
    // also dots and browser action too
    "search": {
        "default": `Ctrl+${modifier}+H`,
        "mac":  `Command+${modifier}+H`
    }
};


// TODO ugh it's getting messy...
const action = {
    "default_icon": "images/ic_not_visited_48.png",
    "default_title": "Was not visited"
};

const manifestExtra = {
    version: pkg.version,
    name: release ? "Were you here?" : "Were you here? (dev)",
    commands: commandsExtra,
    browser_action: action,
};

if (target !== 'chrome') {
    // TODO think if we want page action for desktop Firefox?
    manifestExtra.page_action = action;
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


const buildPath = path.join(__dirname, 'dist', target);

const options = {
  mode: 'development',

  entry: {
    background   : path.join(__dirname, './src/background'),
    options_page : path.join(__dirname, './src/options_page'),
    popup        : path.join(__dirname, './src/popup'),
    sidebar      : path.join(__dirname, './src/sidebar'),
    search       : path.join(__dirname, './src/search'),
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
          test: /\.css$/,
          loader: "style-loader!css-loader",
          exclude: /node_modules/
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
