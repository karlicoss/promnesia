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
}

export default mockBrowser
