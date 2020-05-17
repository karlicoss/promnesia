'''
A more sophisticated example of config for Promnesia
'''

from pathlib import Path

OUTPUT_DIR = Path('/data/promnesia')

from promnesia import Source

# 'auto' indexer tries its best at indexing plaintext stuff
# - plaintext like org-mode/markdown/HTML
# - structured formats like JSON and CSV
from promnesia.sources import auto

# 'guess' indexer can do even more in addition:
# - HTTP links (to index the contents of a website)
# - Github links (to index the contents of a git repository
from promnesia.sources import guess
# TODO there is a very thin link between 'auto' and 'guess'... I mught merge them in the future?


# there are also
# this is an incomplete list, just the (perhaps) most interesting ones
from promnesia.sources import telegram
from promnesia.sources import takeout, instapaper, pocket, fbmessenger, twitter, roamresearch, hypothesis

# now we can specify the sources
# this is a required setting
SOURCES = [
    # handle my knowledge base: extract links from Org-mode and Markdown files
    Source(
        auto.index,
        '/path/to/my/blog',

        # you can specify optional name, so you can see where the URL is coming from in the extension
        name='blog',
    ),

    # we can index another path under a different name (for convenience)
    Source(
        auto.index,
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
    Source(
        telegram.index,
        '/data/telegram/database.sqlite',
        name='tg',
    ),

    ####
    # the following modules are relying on HPI package (https://github.com/karlicoss/HPI#whats-inside) for the data
    # see HPI setup guide: https://github.com/karlicoss/HPI/blob/master/doc/SETUP.org
    # and HPI usage examples': https://github.com/karlicoss/HPI/blob/master/doc/SETUP.org#usage-examples
    Source(takeout.index),
    Source(instapaper.index),
    Source(pocket.index),
    Source(fbmessenger.index),
    Source(twitter.index),
    Source(roamresearch.index),

    # you can also use a lambda
    # sometimes it's useful for config hacking/avoiding early imports
    lambda: Source(hypothesis.index),
]




'''
Optional setting.
A directory to keep intemediate caches in order to speed up indexing.
'''
CACHE_DIR = '/tmp/promnesia_cache/'


'''
Optional setting.
Yu can specify the URLs you don't want to be indexed.
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
