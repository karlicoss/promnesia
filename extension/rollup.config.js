import assert from 'assert'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

import typescript from '@rollup/plugin-typescript'
import { nodeResolve } from '@rollup/plugin-node-resolve'
import commonjs from '@rollup/plugin-commonjs'
import replace from '@rollup/plugin-replace'
import copy from 'rollup-plugin-copy'

import {generateManifest} from './generate_manifest.js'


const target           = process.env.TARGET; assert(target)
const manifest_version = process.env.MANIFEST; assert(manifest_version)
const ext_id           = process.env.EXT_ID; assert(ext_id)
const publish          = process.env.PUBLISH === 'YES'


const thisDir = path.dirname(fileURLToPath(import.meta.url)); assert(path.isAbsolute(thisDir))
const srcDir = path.join(thisDir, 'src')
const buildDir = path.join(thisDir, 'dist', target)


// kinda annoying it's not a builtin..
function cleanOutputDir() {
    return {
        name: 'clean-output-dir',
        buildStart(options) {
            const outDir = buildDir
            // we don't just want to rm -rf outputDir to respect if it's a symlink or something like that
            if (!fs.existsSync(outDir)) {
                return
            }
            fs.readdirSync(outDir).forEach(f => {
                // console.debug("removing %s", f)
                fs.rmSync(path.join(outDir, f), {recursive: true})
            })
        },
    }
}


function generateManifestPlugin() {
    return {
        name: 'generate-manifest',
        generateBundle(outputOptions, bundle) {
            // TODO maybe need to use emitFile instead?
            // docs say "Do not directly add assets to the bundle"
            const manifest = generateManifest({
                target: target,
                manifest_version: manifest_version,
                publish: publish,
                ext_id: ext_id,
            })
            const mjs = JSON.stringify(manifest, null, 2)
            const outputPath = path.join(outputOptions.dir, 'manifest.json')
            fs.mkdirSync(outputOptions.dir, { recursive: true })
            fs.writeFileSync(outputPath, mjs, 'utf8')
        }
    }
}

const shared_plugins = () => [
    // hmm ok this turned out not to be necessary, seems like this works as expected in the newer version
    //replace({
    //    include: ['**/anchorme.js'],
    //    delimiters: ['', ''],
    //    values: Object.fromEntries([
    //        // remove square brackets from link detection regex to support org-mode links
    //        // also see https://github.com/alexcorvi/anchorme.js/compare/gh-pages...karlicoss:anchorme.js:promnesia
    //        [String.raw`\\[\\]`, ''],
    //    ]),
    //    preventAssignment: true,  // will be default soon, atm warns if not true
    //}),
    typescript({
        outDir: buildDir,
        noEmitOnError: true,  // fail on errors
    }),
    nodeResolve(),
    commonjs(),  // needed for webext polyfill
]


const compile = inputs => { return {
    input: inputs,
    output: {
        dir: buildDir,
        chunkFileNames: '[name].js',  // instead of '[name]-[hash].js' -- otherwise the emitted filenames change every time, very annoying for tracking in git

        // huh! so if I build all files in one go, it figures out the shared files properly it seems
        // however it still inlines webextension stuff into one of the files? e.g. common
        manualChunks: id => {  // ugh, seems a bit shit?
            const third_party = [
                'webextension-polyfill',
                'webext-options-sync',
                'codemirror',
                'anchorme',
            ]
            for (const x of third_party) {
                if (id.includes(x)) {
                    return `third_party/${x}`  // move it in a separate chunk
                }
            }
        },
   },
   plugins: [
       cleanOutputDir(),
       copy({
         targets: [
           {src: 'src/**/*.png'          , dest: buildDir},
           {src: 'src/**/*.html'         , dest: buildDir},
           {src: 'src/selenium_bridge.js', dest: buildDir},
           {src: 'src/**/*.css'          , dest: buildDir},
           {src: 'src/toastify.js'       , dest: buildDir},
           {src: 'src/background_chrome_mv2.js', dest: buildDir},
         ],
         flatten: false,
       }),
       ...shared_plugins(),
       generateManifestPlugin(),
   ],
}}

const standalone = inputs => { return {
    input: inputs,
    output: {
        dir: buildDir,
        format: 'iife',
    },
    plugins: [
        replace({
            values: {
                // ugh. necessary for tippyjs since it is referring to some node stuff
                // TODO could use the same for anchorme to replace the regex?
                'process.env.NODE_ENV': JSON.stringify('production'),
            },
            preventAssignment: true,  // will be default soon, atm warns if not true
        }),
       ...shared_plugins(),
    ],
}}


// TODO how to make clean run before everything? and copy to run after compiling everything?
// same with manifest
// pass dummy inputs?
export default [
    // ok, seems like these are executed in order?
    compile([
        path.join(srcDir, 'background.ts'),
        path.join(srcDir, 'options_page.ts'),
        path.join(srcDir, 'search.ts'),
    ]),
    // TODO wonder if could use dynamic import instead of inlining everything?
    // this seemed to kinda work in webpack?
    standalone([
        path.join(srcDir, 'sidebar.ts'),
    ]),
    // have to emit content script separately, otherwise rollup complains about trying to bundle iife
    standalone([
        path.join(srcDir, 'showvisited.js'),
    ]),
]
