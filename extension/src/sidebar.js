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
    console.log(response);

    const doc = document;

    const tbl = doc.createElement('table'); cont.appendChild(tbl);
    tbl.id = 'visits';
    const tbody = doc.createElement('tbody'); tbl.appendChild(tbody);

    const visits = response.visits.map(rvisit =>
        new Visit(
            rvisit.time,
            rvisit.tags,
            rvisit.context,
            rvisit.locator,
        ) // TODO ugh ugly..
    );
    // move visits with contexts on top
    visits.sort((f, s) => (f.context === null ? 1 : 0) - (s.context === null ? 1 : 0));

    // TODO colors for sources would be nice... not sure if server or client provided
    for (const visit of visits) {
        const rep = visit.repr().split(" ");

        const tr = tbl.insertRow(-1);
        const tdd = tr.insertCell(-1);
        tdd.appendChild(doc.createTextNode(rep[0] + " " + rep[1] + " " + rep[2]));
        const tdt = tr.insertCell(-1);
        tdt.appendChild(doc.createTextNode(rep[3]));
        const tds = tr.insertCell(-1);
        tds.appendChild(doc.createTextNode(rep[4]));

        if (visit.context !== null) {
            const context = visit.context;

            const crow = tbl.insertRow(-1);
            crow.classList.add('context');
            const ccell = crow.insertCell(-1);
            ccell.setAttribute('colspan', '3');

            const loc = unwrap(visit.locator);
            const loc_elem = doc.createElement('div');
            loc_elem.classList.add('locator');
            // loc_elem.appendChild(doc.createTextNode(loc));
            // TODO depending on whether it's local or href, generate link..
            // TODO pehaps it's better if backend sends us proper mime handler
            loc_elem.innerHTML = `<a href='emacs:${loc}'>${loc}</a>`;


            const trim_till = Math.min(context.indexOf('\n'), 100);
            const firstline = context.substring(0, trim_till);
            const firstline_elem = doc.createTextNode(firstline);

            const det = doc.createElement('details'); ccell.appendChild(det);
            const summ = doc.createElement('summary'); det.appendChild(summ);

            summ.appendChild(firstline_elem);
            summ.appendChild(loc_elem);
            det.appendChild(doc.createTextNode(context));
        }
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
