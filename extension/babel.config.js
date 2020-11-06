const presets = [
    [
        '@babel/preset-env',
        // https://caniuse.com/usage-table
        {targets: {chrome: 75, firefox: 75}}
    ],
    '@babel/preset-flow',
]
const plugins = []

// if (process.env["ENV"] === "prod") {
//   plugins.push(...);
// }

module.exports = { presets, plugins }
