function requestVisits() {
    chrome.runtime.sendMessage({
        'method':'getVisits'
    }, function(response){
        var table = document.getElementById('visits');
        for (var i in response) {
            var visit = response[i];
            var row = table.insertRow(-1);
            var cell = row.insertCell(0);
            cell.innerHTML = visit;
        }
    });
};

document.addEventListener('DOMContentLoaded', requestVisits);
