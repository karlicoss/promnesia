/* @flow */
import {Visits, Visit, unwrap} from './common';

import React from 'react';
import ReactDOM from 'react-dom';
// $FlowFixMe
import { Frame } from 'chrome-sidebar';

// TODO how to prevent sidebar hiding on click??

const SIDEBAR_ID = "wereyouhere-sidebar";

function toggleSidebar() {
    if (Frame.isReady()) {
        Frame.toggle();
    } else {
        boot();
    }
}
// to make function available for executeScript... gross
window.toggleSidebar = toggleSidebar;


function getSidebarNode(): ?HTMLElement {
    const root = document.getElementById(SIDEBAR_ID);
    // $FlowFixMe
    if (root == null) {
        return null;
    }
    const frame = root.getElementsByTagName('iframe')[0];
    frame.style.background = "rgba(236, 236, 236, 0.4)";

    const cdoc = frame.contentDocument;
    var link = cdoc.createElement("link");
    link.href = chrome.extension.getURL("sidebar.css");
    link.type = "text/css";
    link.rel = "stylesheet";
    cdoc.getElementsByTagName("head")[0].appendChild(link); // TODO why [0]??
    return cdoc.body;
    // right, iframe is pretty convenient for scrolling...

    // const cont = root.children[0].children[1]; // TODO very fragile... div data-reactroot -> some other thing that is an actual container
    // return (cont: HTMLElement);
}

// This is pretty insane... but it's the only sidebar lib I found :(
function clearSidebar() {
    const cont = unwrap(getSidebarNode());
    while (cont.firstChild) {
        cont.removeChild(cont.firstChild);
    }
}

function bindSidebarData(response) {
    const cont = getSidebarNode();
    if (cont == null) {
        console.log('no sidebar, so not binding anything');
        return;
    }
    clearSidebar();

    const doc = document;

    cont.appendChild(doc.createTextNode("Visits:"));
    const tbl = doc.createElement('table'); cont.appendChild(tbl);
    tbl.id = 'visits';
    const tbody = doc.createElement('tbody'); tbl.appendChild(tbody);

    // TODO colors for sources would be nice... not sure if server or client provided
    for (const visit_raw of response.visits) {
        const visit = new Visit(visit_raw.time, visit_raw.tags); // TODO ugh ugly..

        const rep = visit.repr().split(" ");

        // TODO font
        const tr = doc.createElement('tr'); tbody.appendChild(tr);
        const tdd = doc.createElement('td'); tr.appendChild(tdd);
        tdd.appendChild(doc.createTextNode(rep[0] + " " + rep[1] + " " + rep[2]));
        const tdt = doc.createElement('td'); tr.appendChild(tdt);
        tdt.appendChild(doc.createTextNode(rep[3]));
        const tds = doc.createElement('td'); tr.appendChild(tds);
        tds.appendChild(doc.createTextNode(rep[4]));
    }
    cont.appendChild(document.createTextNode("Contexts:"));
    for (const context of response.contexts) {
        const cdiv = document.createElement('div');
        cdiv.innerHTML = `<a href='emacs:${context}'>${context}</a>`;

        cdiv.addEventListener('click', function() {
            chrome.tabs.create({'url': "emacs:" + context, 'active': false});
        });
        cont.appendChild(cdiv);
        // ugh, mime links in href don't seem to work for some reason :(
        // not sure how to trigger it opening without creating new tab, but background isn't too bad
        // TODO hmm maybe they will now!
    }
}
window.bindSidebarData = bindSidebarData;

// TODO ugh, it actually seems to erase all the class information :( is it due to message passing??
function requestVisits() {
    chrome.runtime.sendMessage({
        method: 'getActiveTabVisits'
    }, (response)  => {
        if (response == null) {
            console.log("No visits for this url");
            return;
        }
        bindSidebarData(response);
   });
}


function boot() {
    const sidebar = document.createElement('div');
    sidebar.id = SIDEBAR_ID;
    // $FlowFixMe
    document.body.appendChild(sidebar);

    const App = (
            <Frame/>
    );

    ReactDOM.render(App, sidebar);
    requestVisits();
}

// TODO hmm maybe I don't need any of this iframe crap??
// https://stackoverflow.com/questions/5132488/how-to-insert-script-into-html-head-dynamically-using-javascript
