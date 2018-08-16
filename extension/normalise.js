var R = RegExp;

STRIP_RULES = [
    [R('.*')                     , R('^\\w+://'         )],
    [R('reddit.com|youtube.com') , R('(www|ww|amp)\\.'  )],
    [R('.*')                     , R('[&#].*$'       )],
    [
        [R('^youtube') , null],
        [R('.*')       , R('[\\?].*$')],
    ]
]
;

function normalise_url(url) {
    var cur = url;
    STRIP_RULES.forEach(function (thing) { // meh impure foreach..
        let first = thing[0];
        var rules = null;
        if (first instanceof Array) {
            rules = thing;
        } else {
            rules = [thing];
        }

        for (var i = 0; i < rules.length; i++) {
            let target = rules[i][0];
            let reg = rules[i][1];
            if (target[Symbol.search](cur) >= 0) {
                console.log("%s: matched %s, applying %s", cur, target, reg);
                if (reg !== null) {
                    cur = reg[Symbol.replace](cur, '');
                }
                break;
            }
        }
    });
    return cur;
}
