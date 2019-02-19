const path = require('path');
const webpack = require('webpack');
const CopyWebpackPlugin = require('copy-webpack-plugin'),
      CleanWebpackPlugin = require("clean-webpack-plugin"),
      WebpackExtensionManifestPlugin = require('webpack-extension-manifest-plugin');
const pkg = require('./package.json');
const baseManifest = require('./src/manifest.json');

const options = {
  mode: 'development',

  entry: {
    background   : path.join(__dirname, './src/background'),
    options_page : path.join(__dirname, './src/options_page'),
    popup        : path.join(__dirname, './src/popup'),
    sidebar      : path.join(__dirname, './src/sidebar'),
  },
  output: {
    path: path.join(__dirname, './dist'),
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
      // {
      //     test: new RegExp('\.(' + fileExtensions.join('|') + ')$'),
      //     loader: "file-loader?name=[name].[ext]",
      //     exclude: /node_modules/
      // },
      {
          test: /\.html$/,
          loader: "html-loader",
          exclude: /node_modules/
      }
    ]
  },
  plugins: [
   new CleanWebpackPlugin(["dist/*"]),
   new CopyWebpackPlugin([
      { from: 'images/*' },
      { from: 'src/*.html' , flatten: true},
      { from: 'src/*.css' , flatten: true},
      { from: 'src/toastify.js', flatten: true},
    ]),
    new WebpackExtensionManifestPlugin({
        config: {
            base: baseManifest,
            extend: {version: pkg.version}
        }
    }),
  ]
    //TODO??
  // resolve: {
  //   extensions: ['.js']
  // },
};


module.exports = options;
