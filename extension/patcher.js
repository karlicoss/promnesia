// borrowed from https://github.com/newying61/node-module-patch-source-loader/blob/master/loader.js
const loaderUtils = require('loader-utils')

module.exports.default = function (source) {
  const options = this.getOptions()
  const patches = options.patches;
  for (const patch of patches) {
    let res = source.replace(patch.code, patch.newCode)
    /* TODO crap, apparently it overwrites inplace, so need to restore?
     * e.g. like here.. https://github.com/tugboatcoding/rewrite-source-webpack-plugin/blob/master/src/index.js */
    if (res == source) {
      if (!res.includes(patch.newCode)) { // might be already patched
        throw Error(`Patch ${JSON.stringify(patch)} had no effect`)
      }
    }
    source = res
  }
  return source
}
