# TODO FIXME vendorize canonify
from kython.canonify import canonify

def normalise_url(url):
    return canonify(url)
