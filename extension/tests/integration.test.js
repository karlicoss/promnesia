import {setOptions, getOptions} from '../src/options'

global.chrome = {
    storage: {
        sync: {
            // meh.
            get: function (name, res) {
                res({'options': {
                    host: 'http://badhost:43210', // some random port
                }})
            }
        },
    },
    runtime: {
        lastError: null,
    }
}


test('options', async () => {
    // shouldn't crash at least..
    const opts = await getOptions()
})
// TODO could check options migrations?

import fetch from 'node-fetch'
global.fetch = fetch


import {getBackendVisits} from '../src/api'
test('visits', async() => {
    // const opts = await getOptions()
    // opts.host = host: 'http//bad.host',
   
    // TODO have a defensive and offensive modes?
    // but defensive for network errors makes def makes sense anyway
    const vis = await getBackendVisits()
    expect(vis.visits[0]).toBeInstanceOf(Error)
})
