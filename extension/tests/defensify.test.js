// import {defensify} from '../src/notifications.js';

async function inner() {
    throw 'some_error';
}

async function outer() {
    console.warn('before inner async');
    await inner();
    console.warn('after inner async');
}


function inner2() {
    throw err;
}

function outer2() {
    console.warn('before inner');
    inner2();
    console.warn('after inner');
}

test('defensify', async () => {
    // await alalal();
    // await defensify(alalal)();
    console.log("HIHIH");
    // outer2(); // ok, stack is preserved
    // await outer(); // ugh. stack is lost...
    // const dd = new Date(0);
    // expect(format_dt(dd)).toMatch(/Jan 1 1970/);
});
