from .js_shared import PROTOCOL_REGEXS

def __init_regex():
    import re
    return re.compile(PROTOCOL_REGEXS)

PROTOCOL_REGEX = __init_regex()

def strip_protocol(s):
    return PROTOCOL_REGEX.sub('', s)


def normalise_url(s):
    return strip_protocol(s)
