// this is to prevent tests failing on importing browser polyfill
// see https://stackoverflow.com/questions/73809020/cant-mock-webextension-polyfill-for-jest-unit-tests
import { jest } from "@jest/globals"

const mockBrowser = {
  history: {
    getVisits: jest.fn(),
    search   : jest.fn(),
  },
  bookmarks: {
    getTree: jest.fn(),
  },
  storage: {
    sync: {
      // meh.
      get: (name, res) => {
        res({'options': {
          host: 'http://badhost:43210', // some random port, to cause it fail
        }})
      }
    },
  },
  runtime: {
    lastError: null,
    getManifest    : () => { return {version: 'whatever'} },
    getPlatformInfo: async () => {},
  },
}

export default mockBrowser
