import * as linkify from 'linkifyjs'
import { registerOrgBracketsPlugin } from '../src/display'


test('detects links correctly', () => {
    registerOrgBracketsPlugin()

    const data = `
Normal links should work as expected: https://example.com/whatever

without the fix, if you have text like this:

[[https://wiki.openhumans.org/wiki/Personal_Science_Wiki][Personal Science Wiki]]

- more text

should handle this one: somewebsite.org

and [markdown](https://www.markdownguide.org/basic-syntax/) should work as well
`
    const res = linkify.find(data, {defaultProtocol: 'https'}).map(o => o.href)
    expect(res).toStrictEqual([
        'https://example.com/whatever',
        'https://wiki.openhumans.org/wiki/Personal_Science_Wiki',
        'https://somewebsite.org',
        'https://www.markdownguide.org/basic-syntax/',
    ])
})
