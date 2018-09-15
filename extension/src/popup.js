function requestVisits() {
    chrome.runtime.sendMessage({
        'method':'getVisits'
    }, function(response){
        if (response == null) {
            console.log("No visits for this url");
            return;
        }

        console.log(response);
        var visits_table = document.getElementById('visits');
        var visits = response.visits;
        for (var i in visits) {
            var visit = visits[i];
            var row = visits_table.insertRow(-1);
            var cell = row.insertCell(0);
            cell.innerHTML = visit;
        }

        var contexts_table = document.getElementById('contexts');
        // TODO ugh, JS: can i just ignore redeclaration??
        var contexts = response.contexts;
        for (i in contexts) {
            var context = contexts[i];
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
