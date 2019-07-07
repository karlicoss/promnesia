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

const target = env.TARGET;
const release = env.RELEASE == 'YES' ? true : false;


const manifestExtra = {
    version: pkg.version,
    name: release ? "Were you here?" : "Were you here? (dev)",
};

if (target == 'chrome') {
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
