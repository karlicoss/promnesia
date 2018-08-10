
var R = RegExp;

STRIP_RULES = [
    [R('.*')        , R('^\\w+://'         )],
    [R('.*')        , R('[&#\\?].*$'       )],
    [R('reddit.com'), R('(www|ww|amp)\\.'  )],
];


function normalise_url(url) {
    var cur = url;
    STRIP_RULES.forEach(function (xx) { // meh impure foreach..
        let target = xx[0];
        let reg = xx[1];
        if (target[Symbol.search](cur) >= 0) {
            cur = reg[Symbol.replace](cur, '');
        }
    });
    return cur;
}
