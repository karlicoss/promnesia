Has it ever occured to you that you were reading an old bookmark or some lengthy blog post and suddenly realized you had read it already before? It would be fairly easy to search in chrome history, however it is only stored locally for three months. 

Or perhaps you even have a habit of annotating and making notes elsewhere? And you wanna know quickly if you have the current page annotated. Then this tool is for you.

The Chrome extension consumes a JSON file with history. It may be generated from:

* local sqlite history database backups
* Google Takeout/Activity backups
* custom shell command 
* [todo] file system link extractors
* in general, it's super extendable. It's JSON, duh!

# Configuring
* generator: TODO `cp config.py.example config.py`, edit config.py, run `python3 -m wereyouhere`
then, see the comments in the `config.py` for more information on using various history sources.
* extension: choose the generated JSON in the extension settings

# Running
To generate the URL database, run:

    ./generate
    
To use chrome extension, just 'load unpacked' on chrome://extensions/

# TODOs

* [in progress] commit scripts to process history sources
* [in progress] collect from filesystem
* [in progress] use chrome history too
* [in progress] be more informative; show full history or at least last visit and potentially sources (e.g. hypothesis)
  * maybe icons for mobile/desktop?
* use some sort of smarter matching, e.g. no difference between http and https; normalise, remove trailing slash, etc, ignore some schemas/urls
  * use some python lib to extract normalised urls? there must be something.. however normalisation has to be simple enough, so JS site could use it too.
* handle url-decoding propely
* merge chrome db backups to avoid duplication
