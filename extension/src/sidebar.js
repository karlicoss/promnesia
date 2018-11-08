/* @flow */
import {Visits, Visit} from './common';

import React from 'react';
import ReactDOM from 'react-dom';
// $FlowFixMe
import { Frame } from 'chrome-sidebar';

if (Frame.isReady()) {
    Frame.toggle();
} else {
    boot();
}

// TODO ugh, why does variable not work??
const SIDEBAR_ID = "wereyouhere-sidebar";

function getSidebarNode() {
    const root = document.getElementById(SIDEBAR_ID);
    // $FlowFixMe
    const cont = root.children[0].children[1]; // TODO very fragile...
    return cont;
}

// This is pretty insane... but it's the only sidebar lib I found :(
function clearUpSidebar() {
    const cont = getSidebarNode();
    const ifr = cont.getElementsByTagName('iframe')[0];
    cont.removeChild(ifr);
    cont.style.backgroundColor = "rgba(236, 236, 236, 0.4)";
    cont.style.fontSize = "16px";
}

// TODO move to common??
// TODO ugh, it actually seems to erase all the class information :( is it due to message passing??
function requestVisits() {
    chrome.runtime.sendMessage({
        'method':'getVisits'
    }, (response)  => {
        if (response == null) {
            console.log("No visits for this url");
            return;
        }
        // TODO shit, would I need to parse dates again? Hopefully datetime is not erased...

        clearUpSidebar();

        const cont = getSidebarNode();

        // TODO css override?
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
   });
}

function boot() {
    const sidebar = document.createElement('div');
    sidebar.id = "wereyouhere-sidebar";
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
//     const ifr = root.getElementsByTagName('iframe')[0];
//     ifr.srcdoc = `
// <html>
// <head></head>
// <body onload="hi(); requestVisits();">

// WHAAT
// <script>
// function hi () {
//   console.log('runtime', chrome.runtime);
//   console.log('hiiiiii');
// }

// </script>

// </body>
// </html>
// `;
// const doc = ifr.contentWindow.document;
// // TODO onload??
// doc.open();
// doc.write();
// doc.close();

// const scr = doc.createElement('script');
// scr.async = false;
// scr.text = 'function LogIt(msg) { console.log(msg);}';
// scr.onload = function () {
//     LogIt('WHHHAAAT');
// };
// doc.head.appendChild(scr);
// TODO jeez, that's quite an ugly way to inject content... but whatever...
