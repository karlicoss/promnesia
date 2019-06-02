/* @flow */
import {Visits, Visit, unwrap, format_dt} from './common';
import type {Tag, Locator} from './common';
import {get_options} from './options';

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
    const link = cdoc.createElement("link");
    link.href = chrome.extension.getURL("sidebar.css");
    link.type = "text/css";
    link.rel = "stylesheet";
    const head  = cdoc.getElementsByTagName("head")[0]; // TODO why [0]??
    head.appendChild(link);

    // make links open in new tab instead of iframe https://stackoverflow.com/a/2656798/706389
    const base = cdoc.createElement('base');
    base.setAttribute('target', '_blank');
    head.appendChild(base);

    return cdoc.body;
    // right, iframe is pretty convenient for scrolling...

    // const cont = root.children[0].children[1]; // TODO very fragile... div data-reactroot -> some other thing that is an actual container
    // return (cont: HTMLElement);
}

function get_or_default(obj, key, def) {
    const res = obj[key];
    return res === undefined ? def : res;
}

// This is pretty insane... but it's the only sidebar lib I found :(
function clearSidebar() {
    const cont = unwrap(getSidebarNode());
    while (cont.firstChild) {
        cont.removeChild(cont.firstChild);
    }
}

function _fmt(dt: Date): [string, string] {
    // TODO if it's this year, do not display year?
    const dts = format_dt(dt);
    const parts = dts.split(' ');
    const datestr = parts.slice(0, 3).join(' ');
    const timestr = parts.slice(3).join(' ');
    return [datestr, timestr];
}

function bindSidebarData(response) {
    get_options(opts => bindSidebarDataAux(response, opts));
}

function bindSidebarDataAux(response, opts) {
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

    // TODO why has this ended up serialised??
    const visits = response.visits.map(rvisit =>
        new Visit(
            new Date(rvisit.time),
            rvisit.tags,
            rvisit.context,
            rvisit.locator,
        ) // TODO ugh ugly..
    );
    visits.sort((f, s) => (s.time - f.time));

    // move visits with contexts on top
    const with_ctx = [];
    const no_ctx = [];
    for (const v of visits) {
        if (v.context === null) {
            no_ctx.push(v);
        } else {
            with_ctx.push(v);
        }
    }

    function handle(
        dates: string,
        times: string,
        tags: Array<Tag>,
        context: ?string=null,
        locator: ?Locator=null
    ) {
        const tr = tbl.insertRow(-1);
        const tdd = tr.insertCell(-1);
        tdd.appendChild(doc.createTextNode(dates));
        const tdt = tr.insertCell(-1);
        tdt.appendChild(doc.createTextNode(times));
        const tds = tr.insertCell(-1);
        const tagss = tags.join(':');
        tds.appendChild(doc.createTextNode(tagss));

        if (context != null) {
            const crow = tbl.insertRow(-1);
            crow.classList.add('context');
            const ccell = crow.insertCell(-1);
            ccell.setAttribute('colspan', '3');

            const loc = unwrap(locator);
            const loc_elem = doc.createElement('span');
            loc_elem.classList.add('locator');
            // loc_elem.appendChild(doc.createTextNode(loc));
            // TODO depending on whether it's local or href, generate link..
            // TODO pehaps it's better if backend sends us proper mime handler
            // TODO yep, definitely backend needs to give us text and href
            // TODO dispatch depending on having href
            // TODO need escaping?
            loc_elem.innerHTML = loc.href == null ? loc.title : `<a href='${loc.href}'>${loc.title}</a>`;


            const trim_till = Math.min(context.indexOf('\n'), 100);
            const firstline = context.substring(0, trim_till);
            const firstline_elem = doc.createTextNode(firstline);

            const det = doc.createElement('details'); ccell.appendChild(det);
            const summ = doc.createElement('summary'); det.appendChild(summ);

            summ.appendChild(loc_elem);
            // TODO not sure if we want to do anything if we have trimmed locator...
            // TODO at least add some space?
            summ.appendChild(firstline_elem);
            det.appendChild(doc.createTextNode(context));
        }
    }

    // TODO colors for sources would be nice... not sure if server or client provided
    for (const v of with_ctx) {
        const [dates, times] = _fmt(v.time);
        handle(dates, times, v.tags, v.context, v.locator);
    }


    var groups = [];
    var group = [];

    function dump_group () {
        if (group.length > 0) {
            groups.push(group);
            group = [];
        }
    }

    const delta = 20 * 60 * 1000;
    for (const v of no_ctx) {
        const last = group.length == 0 ? v : group[group.length - 1];
        if (last.time - v.time > delta) {
            dump_group();
        }
        group.push(v);
    }
    dump_group();

    const tag_map = opts.tag_map;
    // TODO group ones with no ctx..
    for (const group of groups) {
        const first = group[0];
        const last  = group[group.length - 1];
        const [fdates, ftimes] = _fmt(first.time);
        const [ldates, ltimes] = _fmt(last.time);
        const dates = ldates;
        const times = ltimes == ftimes ? ltimes : ltimes + "-" + ftimes;
        const tset = new Set();
        for (const v of group) {
            for (const tag of v.tags) {
                const mapped_tag = get_or_default(tag_map, tag, tag);
                tset.add(mapped_tag);
            }
        }
        const tags = [...tset];
        handle(dates, times, tags);
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
