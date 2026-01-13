- manifest version: both chrome and firefox store versions are on manifest v3 now

# permissions used
See `PRIVACY.org`.

# `package.json` comments
## browserslist
Not used by the extension (since `rollup-plugin-typescript` is looking at `tsconfig.json`), but it's used by babel/jest?

## devDependencies

- **@babel/core**, **@babel/preset-env**, **@babel/preset-typescript**: only needed for eslint, extension code is handled by typescript
- **@eslint/js**: eslint configs
- **@rollup/plugin-commonjs**: needed for webext polyfill
- **@rollup/plugin-node-resolve**: for Rollup to find modules in `node_modules`
- **@rollup/plugin-replace**: for patching up some dependencies
- **@rollup/plugin-typescript**
- **@types/webextension-polyfill**: typescript definitions for the browser extension APIs
- **chrome-webstore-upload-cli**: automate publishing to the Chrome Web Store
- **eslint**: linter
- **globals**: browser `globals` for eslint
- **jest**: testing framework
- **jest-environment-jsdom**: simulates a DOM environment for testing
- **jest-fetch-mock**: mock `fetch` calls in tests
- **node-fetch**: used in testing, but not really sure why? I though I used mocks
- **rollup**: module bundler used to compile the extension
- **rollup-plugin-copy**: copies static files (HTML, images) to the output directory
- **tslib**: runtime helpers for typescript
- **typescript**
- **typescript-eslint**: enables eslint to support typescript
- **web-ext**: Mozilla's command-line tool for running, linting, and building extensions
- **webextension-polyfill**: Promise-based `browser` API to make things consistent across chrome and firefox

## "type": "module"
This is to enable ES modules (ESM) in Node.js.
- allows using `import`/`export` in `rollup.config.js` and other build scripts.
- requires CommonJS config files (like `jest.config.cjs`) to use the `.cjs` extension.
