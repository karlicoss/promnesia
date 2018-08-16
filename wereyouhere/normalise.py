from re import compile as R

STRIP_RULES = [
    [R('.*')                     , R('^\\w+://'         )],
    [R('reddit.com|youtube.com') , R('(www|ww|amp)\\.'  )],
    [R('.*')                     , R('[&#].*$'       )],
    [
        [R('^youtube') , None],
        [R('.*')       , R('[\\?].*$')],
    ]
]


def normalise_url(url):
    cur = url
    for thing in STRIP_RULES:
        first = thing[0]
        rules = None
        if isinstance(first, list):
            rules = thing
        else:
            rules = [thing]

        for target, reg in rules:
            if target.search(cur):
                if reg is not None:
                    cur = reg.sub('', cur)
                break


    return cur


# use [] instead of () so it's easy to copy regexes to js
# TODO eh, None vs null..

# TODO fine tune, start with reddit?
# TODO ok, if first elemnent is a rule, apply it
# if only one, bail
# if it's a list, they are mutually exclusive?
