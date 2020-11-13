import {setOptions, getOptions} from '../src/options'

global.chrome = {
    storage: {
        sync: {
            // meh.
            get: (name, res) => {
                res({'options': {
                    host: 'http://badhost:43210', // some random port
                }})
            }
        },
    },
    runtime: {
        lastError: null,
        getPlatformInfo: (res) => { res({}) },
    }
}


test('options', async () => {
    // shouldn't crash at least..
    const opts = await getOptions()
})
// TODO could check options migrations?

import fetch from 'node-fetch'
global.fetch = fetch


import {backend} from '../src/api'
test('visits', async() => {
    // const opts = await getOptions()
    // opts.host = host: 'http//bad.host',
   
    // TODO have a defensive and offensive modes?
    // but defensive for network errors makes def makes sense anyway
    const vis = await backend.visits('http://123.com')
    // FIXME test specific error?
    expect(vis).toBeInstanceOf(Error)
})


import {allsources} from '../src/sources'


// meh.
global.chrome.history = {
    getVisits: (obj, res) => res([]),
}
global.chrome.bookmarks = {
    getTree: (res) => res([{
        children: [{
            url: 'http://whatever.com/',
            dateAdded: 16 * 10 ** 8 * 1000,
        }],
    }]),
}

test('visits_allsources', async() => {
    const vis = await allsources.visits('https://whatever.com/')
    expect(vis.visits).toHaveLength(2)
    expect(vis.normalised_url).toStrictEqual('whatever.com')
})

import fetchMock from 'jest-fetch-mock'
// TODO use it as a fixture..
// beforeEach(() => {
//   fetch.resetMocks()
// })

test('visits_badresponse', async() => {
    fetchMock.enableMocks()
    fetchMock.mockResponse({body: 'bad!'})
    const res = await backend.visits('http://mock.com')
    expect(res).toBeInstanceOf(Error)
})
