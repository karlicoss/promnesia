from re import compile as R

STRIP_RULES = [
    (R('.*')         , R('^\\w+://'         )), # protocol
    (R('.*')         , R('[&#\\?].*$'       )), # query
    (R('reddit.com') , R('(www|ww|amp)\\.'  )),
]
# TODO fine tune, start with reddit?

def normalise_url(url):
    cur = url
    for target, reg in STRIP_RULES:


        if target.search(cur):
            cur = reg.sub('', cur)


    return cur
