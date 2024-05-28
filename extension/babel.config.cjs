const presets = [
    // this is necessary for jest? otherwsie it can't import modules..
    // ugh... I don't understand tbh, seems that even without preset-env, webpack respects browserlist??
    // and looks like without preset-env the code is cleaner???
    // but whatever, the difference is minor and I don't have energy to investigate now..
    '@babel/preset-env',

    // also necessary for jest? otherwise fails to import typescript
    '@babel/preset-typescript',
]
const plugins = []

// if (process.env["ENV"] === "prod") {
//   plugins.push(...);
// }

module.exports = { presets, plugins }
