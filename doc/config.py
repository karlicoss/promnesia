'''
A more sophisticated example of config for Promnesia
'''

from promnesia.common import Source


# now, let's import some indexers
# NOTE: you might need extra dependencies before using some of the indexers
# see https://github.com/karlicoss/HPI/blob/master/doc/SOURCES.org

# 'auto' indexer tries its best at indexing plaintext stuff
# - plaintext like org-mode/markdown/HTML
# - structured formats like JSON and CSV
from promnesia.sources import auto

# 'guess' indexer can do even more in addition:
# - HTTP links (to index the contents of a website)
# - Github links (to index the contents of a git repository
from promnesia.sources import guess
# TODO there is a very thin link between 'auto' and 'guess'... I might merge them in the future?


# this is an incomplete list, just the (perhaps) most interesting ones
from promnesia.sources import telegram
from promnesia.sources import (
    fbmessenger,
    hypothesis,
    instapaper,
    pocket,
    roamresearch,
    rss,
    takeout,
    twitter,
    viber,
    signal,
)


# NOTE: at the moment try to avoid using complex sources names
# it's best to stick to digits, latin characters, dashes and underscores
# there might be some UI problems related to that

# now we can specify the sources
# this is a required setting
SOURCES = [
    # handle my knowledge base: extract links from Org-mode and Markdown files
    Source(
        auto.index,
        # NOTE: you'd need to specify your own filesystem path here
        '/path/to/my/blog',

        # you can specify optional name, so you can see where the URL is coming from within the extension
        name='blog',
    ),

    # we can index another path under a different name (for convenience)
    Source(
        auto.index,
        # NOTE: you'd need to specify your own filesystem path here
        '/path/to/personal/notes',
        ignored=['*.html'],  # we can exclude certain files if we want

        name='notes',
    ),


    # will clone the repository and index its contents!
    Source(
        guess.index, # you could also use 'vcs.index', but auto can handle it anyway
        'https://github.com/karlicoss/exobrain',
        name='exobrain',
    ),


    # Uses the output of telegram_backup tool: https://github.com/fabianonline/telegram_backup#usage
    # name will be set to 'telegram' by default
    Source(
        telegram,
        '/data/telegram/database.sqlite',
        #http_only=None  # harvest alsoIP-addresses & plain domain-names
    ),

    # Uses all local SQLite files found in your Viber Desktop configurations
    # (one directory for each telephone number):
    #     ~/.ViberPC/**/viber.db
    #
    # You may modify that by providing a 2nd ``Source()`` argument.
    Source(
        viber,
        #"path/to/viber-sql",
        #http_only=None  # harvest alsoIP-addresses & plain domain-names
    ),

    # When path(s) given, uses the SQLite inside Signal-Desktop's configuration directory
    # (see the sources for more parameters & location of the db-file for each platform)
    signal,

    # NOTE: to configure the following modules you need to set up HPI package (https://github.com/karlicoss/HPI#whats-inside)
    # see HPI setup guide    : https://github.com/karlicoss/HPI/blob/master/doc/SETUP.org
    # and HPI usage examples': https://github.com/karlicoss/HPI/blob/master/doc/SETUP.org#usage-examples
    ####
    Source(hypothesis.index),
    Source(takeout.index),

    # you can also be less verbose in config, if you prefer
    Source(roamresearch),
    Source(rss, name='custom name'),

    # or:
    fbmessenger.index,

    # or even just:
    pocket,
    instapaper,


    # sometimes lambdas are useful for config hacking/avoiding early imports
    lambda: twitter.index(),
]



''''
Optional setting.
A directory where promnesia.sqlite will be stored.
If not specified, user data directory is used, e.g. ~/.local/share/promnesia/
see https://github.com/ActiveState/appdirs#some-example-output for different OS
'''
OUTPUT_DIR = '/data/promnesia'

'''
Optional setting.
A directory to keep intemediate caches in order to speed up indexing.
If not specified, will use user cache directory
If set to None, cache is disabled
'''
CACHE_DIR = '/tmp/promnesia_cache/'


'''
Optional setting.
You can specify the URLs you don't want to be indexed.
You might want it because there are too many of them, or for security/privacy reasons.
'''
FILTERS = [
    'mail.google.com',
    'web.telegram.org/#/im',
    'vk.com/im',
    '192.168.0.',

    # you can use regexes too!
    'redditmedia.com.*.(jpg|png|gif)',
]

'''
Optional setting.
Can be useful to hack (e.g. rewrite/filter/etc) the visits before inserting in the database.
'''
def HOOK(v):
    # filter out 'boring' github visits without contexts
    if 'github.com' in v.norm_url:
        if v.context is None:
            return
    # otherwise keep intact
    yield v
