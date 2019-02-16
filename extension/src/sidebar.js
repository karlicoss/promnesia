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
    const cont = root.children[0].children[1]; // TODO very fragile... div data-reactroot -> some other thing that is an actual container
    return (cont: HTMLElement);
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

    // TODO align somehow??
    cont.appendChild(document.createTextNode("Visits:"));
    for (const visit_raw of response.visits) {
        const visit = new Visit(visit_raw.time, visit_raw.tags); // TODO ugh ugly..

        const vdiv = document.createElement('div');
        vdiv.innerText = visit.repr();
        cont.appendChild(vdiv);
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

    var link = document.createElement("link");
    link.href = chrome.extension.getURL("sidebar.css");
    link.type = "text/css";
    link.rel = "stylesheet";
    document.getElementsByTagName("head")[0].appendChild(link); // TODO why [0]??

    const App = (
            <Frame/>
    );

    ReactDOM.render(App, sidebar);
    requestVisits();
}

// TODO hmm maybe I don't need any of this iframe crap??
// https://stackoverflow.com/questions/5132488/how-to-insert-script-into-html-head-dynamically-using-javascript
