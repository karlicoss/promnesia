Has it ever occured to you that you were reading an old bookmark or some lengthy blog post and suddenly realized you had read it already before? It would be fairly easy to search in chrome history, however it is only stored locally for three months. 

Or perhaps you even have a habit of annotating and making notes elsewhere? And you wanna know quickly if you have the current page annotated. Then this tool is for you.

The Chrome extension consumes a JSON file with history. It may be generated from:

* local sqlite history database backups
* TODO Google Takeout/Activity backups
* TODO or anything else with a simple script. It's JSON, duh!

# Configuring
* generator: TODO `cp config.py.example config.py`, edit config.py, run `python3 -m wereyouhere`
* extension: TODO go to settings, choose the file

# TODOs
* commit scripts to process history sources
* use chrome history too
* [in progress] be more informative; show full history or at least last visit and potentially sources (e.g. hypothesis)
* use some sort of smarter matching, e.g. no difference between http and https
* at the moment workflow is: go to options; set the path, reload extensions. do that right.
* use thicker icons
