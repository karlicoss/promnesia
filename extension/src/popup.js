/* @flow */
import {Visits, Visit} from './common';


function requestVisits() {
    chrome.runtime.sendMessage({
        'method':'getVisits'
    }, function(response: ?Visits) {
        if (!response) {
            console.log("No visits for this url");
            return;
        }

        console.log(response);
        var visits_table = document.getElementById('visits');
        const visits = response.visits;
        // flow can't handle arrays?
        // $FlowFixMe
        for (const i in visits) {
            const visit: Visit = visits[i];
            // $FlowFixMe
            var row = visits_table.insertRow(-1);
            var cell = row.insertCell(0);
            cell.innerHTML = visit.repr();
        }

        var contexts_table = document.getElementById('contexts');
        // TODO ugh, JS: can i just ignore redeclaration??
        var contexts = response.contexts;
        // flow can't handle arrays?
        // $FlowFixMe
        for (const i in contexts) {
            var context = contexts[i];
            // $FlowFixMe
            row = contexts_table.insertRow(-1);
            cell = row.insertCell(0);
            // ugh, mime links in href don't seem to work for some reason :(
            // not sure how to trigger it opening without creating new tab, but background isn't too bad
            cell.addEventListener('click', function() {
                chrome.tabs.create({'url': "emacs:" + context, 'active': false});
            });
            cell.innerHTML = "<a href='emacs:" + context + "'>" + context + "</a>";
        }
    });
}

document.addEventListener('DOMContentLoaded', requestVisits);
