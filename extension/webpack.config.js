const path = require('path');
const webpack = require('webpack');
const CopyWebpackPlugin = require('copy-webpack-plugin');
const WebpackExtensionManifestPlugin = require('webpack-extension-manifest-plugin');
const pkg = require('./package.json');
const baseManifest = require('./src/manifest.json');

module.exports = {
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
  plugins: [
    new CopyWebpackPlugin([
      { from: 'images/*' },
      { from: 'src/*.html' , flatten: true},
    ]),
    new webpack.DefinePlugin({
      'process.env': {
        NODE_ENV: JSON.stringify('production')
      }
    }),
    new WebpackExtensionManifestPlugin({
        config: {
            base: baseManifest,
            extend: {version: pkg.version}
        }
    }),
  ],
  resolve: {
    extensions: ['.js']
  },
  module: {
    loaders: [{
      test: /\.js$/,
      loader: 'babel-loader',
      query: {
        presets: ['react', 'es2015', 'stage-0']
      },
      exclude: /node_modules/
    }]
  }
}
