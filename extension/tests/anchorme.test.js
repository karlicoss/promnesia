import anchorme from "anchorme"

test('detects org-mode links correctly', () => {
    const res = anchorme.list(`
without the fix, if you have text like this:

[[https://wiki.openhumans.org/wiki/Personal_Science_Wiki][Personal Science Wiki]]

- also delete the min.js file because I'm not sure how to patch it -- to prevent using it by accident
`).map(o => o.string)
    expect(res).toStrictEqual(['https://wiki.openhumans.org/wiki/Personal_Science_Wiki'])
})
