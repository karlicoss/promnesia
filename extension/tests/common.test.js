const common = require('../src/common');

// https://jestjs.io/docs/en/using-matchers
test('formats date', () => {
    const dd = new Date(0);
    expect(common.format_dt(dd)).toMatch(/Jan 1 1970/);
});

import {normalise_url} from '../src/normalise.js';

test('normalises', () => {
    expect(normalise_url('https://www.youtube.com/playlist?list=PLWz5rJ2EKKc9CBxr3BVjPTPoDPLdPIFCE/')).toBe('youtube.com/playlist?list=PLWz5rJ2EKKc9CBxr3BVjPTPoDPLdPIFCE');
});
