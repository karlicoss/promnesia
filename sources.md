Sources of data for populating database.

# Local database

Chrome used to have 'Archived History' database, but not anymore: https://superuser.com/questions/414346/how-can-i-view-archived-google-chrome-history-i-e-history-older-than-three


# Google Takout

Couldn't find any decent documentation for every particular bit of it. Sometimes it overlaps with local browser history, sometimes doesn't; sometimes files overlap among each other. Looks like it's useful to populate from all of them.

* `Chrome/BrowserHistory.json`
My takeout from april 2018 had stuff in this file up to February 2017. Kinda arbitrary!

    grep -c "LINK" BrowserHistory.json
    148678

* `My Activity/Chrome/MyActivity.html`
Everything is prefixed with google search for some reason.

    grep -o 'Visited' MyActivity.html | wc -l
    87273

* `My Activity/Search/MyActivity.html`
This file had stuff up to April 2014. Again, looks arbitrary.

    grep -o 'Visited' MyActivity.html | wc -l
    72813
