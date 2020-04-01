import {format_dt, format_duration} from '../src/common.js';

// https://jestjs.io/docs/en/using-matchers
test('formats date', () => {
    const dd = new Date(Date.UTC(2018, 11, 1, 10, 15, 0));
    expect(format_dt(dd)).toMatch(/1 Dec 2018 10:15/);
});

test('formats duration', () => {
    expect(format_duration(40)).toBe('40 seconds');
    expect(format_duration(124)).toBe('2 minutes');
    expect(format_duration(24 * 60 * 60 + 95 * 60 + 20)).toBe('25 hours 35 minutes');
});

import {normalise_url} from '../src/normalise.js';

test('normalises', () => {
    expect(normalise_url('https://www.youtube.com/playlist?list=PLWz5rJ2EKKc9CBxr3BVjPTPoDPLdPIFCE/')).toBe('youtube.com/playlist?list=PLWz5rJ2EKKc9CBxr3BVjPTPoDPLdPIFCE');
});


import {normalisedURLHostname} from '../src/normalise.js';
test('normalisedURLHostname', () => {
    expect(normalisedURLHostname('https://www.reddit.com/whatever')).toBe('reddit.com');
    expect(normalisedURLHostname('file:///usr/share/doc/python3/html/index.html')).toBe('');
});


import {Blacklist} from '../src/blacklist.js';


test('blacklist membership', () => {
    // TODO make tests literate so they contribute to help docs?
    const bl_string = `
mail.google.com
https://vk.com
**github.com/issues**
/github.com/issues.*/
`;

    const b = new Blacklist(bl_string);

    // TODO eh, doesn't work with links without schema; not sure if it's ok
    expect(b._helper('http://instagram.com/')).toBe(null);

    // whole domain is blocked
    expect(b._helper('https://mail.google.com/mail/u/0/#inbox')).toContain('domain');


    // specific page is blocked
    expect(b._helper('https://vk.com')).toContain('page');
    // TODO test with trailing slash as well??
    expect(b._helper('https://vk.com/user/whatever')).toBe(null);


    // wildcard blockig
    expect(b._helper('http://github.com/')).toBe(null);
    expect(b._helper('http://github.com/issues/hello/123')).toContain('regex');

    // TODO later, doesn't work ATM
    // expect(b._helper('http://github.com/issues/hello/123', bl)).toContain('wildcard');
});
