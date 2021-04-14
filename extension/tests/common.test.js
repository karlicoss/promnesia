import {_fmt} from '../src/display.js'

test('formats visit date/time', () => {
    // NOTE: under Node env there might not be necessary locales (e.g. if you're running in Docker)
    // can check with: Intl.DateTimeFormat('en-GB').resolvedOptions().locale
    // e.g. it might resolve to incmplete locale like 'en'
    const dd = new Date('05 Jun 2020 05:58:00') // deliberately no timezone, it's pointless without the backend anyway
    const [ds, ts] = _fmt(dd)
    expect(ds).toBe('5 Jun 2020')
    expect(ts).toBe('05:58')
})

import {format_duration} from '../src/common.js'

test('formats duration', () => {
    expect(format_duration(40)).toBe('40 seconds');
    expect(format_duration(124)).toBe('2 minutes');
    expect(format_duration(24 * 60 * 60 + 95 * 60 + 20)).toBe('25 hours 35 minutes');
});


import {Visits} from '../src/common'
import {makeFakeVisits} from '../src/api'

test('visits', () => {
    for (const vis of [
        [],
        makeFakeVisits(1).visits,
        makeFakeVisits(10).visits,
        [new Error('some error')],
        [new Error('other error'), ...makeFakeVisits(2).visits],
    ]) {
        const v = new Visits('http://test', 'http://test', vis)
        const vv = Visits.fromJObject(v.toJObject())
        expect(v).toStrictEqual(vv)
    }

    // test for more elaborate error handling, make sure it preserves stack
    // apparently Error comparison doesn't do anything to the stack..
    for (const vis of [
        [function () {
            const err = new Error('some message')
            err.stack = 'stack1\nstack2'
            return err
        }()],
    ]) {
        const v = new Visits('http://test', 'http://test', vis)
        const vv = Visits.fromJObject(v.toJObject())
        const e = vv.visits[0]
        expect(e.stack).toStrictEqual('stack1\nstack2')
    }
})

import {normalise_url} from '../src/normalise.js';

test('normalises', () => {
    expect(normalise_url('https://www.youtube.com/playlist?list=PLWz5rJ2EKKc9CBxr3BVjPTPoDPLdPIFCE/')).toBe('youtube.com/playlist?list=PLWz5rJ2EKKc9CBxr3BVjPTPoDPLdPIFCE');
});


import {normalisedURLHostname} from '../src/normalise.js';
test('normalisedURLHostname', () => {
    expect(normalisedURLHostname('https://www.reddit.com/whatever')).toBe('reddit.com');
    expect(normalisedURLHostname('file:///usr/share/doc/python3/html/index.html')).toBe('');
});


import {Filterlist} from '../src/filterlist.js'


test('filterlists', async () => {
    // TODO make tests literate so they contribute to help docs?
    const bl_string = `
mail.google.com
https://vk.com
**github.com/issues**
/github.com/issues.*/

//comment.com

https://reddit.com/

`

    const b = new Filterlist({filterlist: bl_string, urllists_json: '[]'})

    // TODO eh, doesn't work with links without schema; not sure if it's ok
    expect(await b.contains('http://instagram.com/')).toBe(null)

    // whole domain is blocked
    expect(await b.contains('https://mail.google.com/mail/u/0/#inbox')).toContain('domain')


    // specific page is blocked
    expect(await b.contains('https://vk.com' )).toContain('exact page')
    expect(await b.contains('https://vk.com/')).toContain('exact page')
    expect(await b.contains('https://vk.com/user/whatever')).toBe(null)
    expect(await b.contains('https://reddit.com')).toContain('exact page')

    // wildcard blockig
    expect(await b.contains('http://github.com/')).toBe(null)
    expect(await b.contains('http://github.com/issues/hello/123')).toContain('regex')

    // TODO later, doesn't work ATM
    // expect(b.contains('http://github.com/issues/hello/123', bl)).toContain('wildcard');

    expect(await b.contains('123456')).toBe('invalid URL')
    expect(await b.contains('http://comment.com')).toBe(null)
})
