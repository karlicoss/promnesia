/* @flow */

import {unwrap} from './common';
import type {Visits} from './common';
import {searchVisits, searchAround} from './background';
import {Binder, _fmt} from './display';


const doc = document;

function getInputElement(element_id: string): HTMLInputElement {
    return ((doc.getElementById(element_id): any): HTMLInputElement);
}

function getQuery(): HTMLInputElement {
    return getInputElement('query_id');
}

function getResultsContainer(): HTMLElement {
    return ((doc.getElementById('visits'): any): HTMLElement);
}


function clearResults() {
    const res = getResultsContainer();
    while (res.firstChild) {
        res.removeChild(res.firstChild);
    }
}

function showError(err) {
    clearResults();
    const res = getResultsContainer();
    const err_c = doc.createElement('div'); res.appendChild(err_c);
    err_c.classList.add('error');
    const err_text = doc.createTextNode(err); err_c.appendChild(err_text);
}


async function _doSearch(cb: Promise<Visits>) {
    clearResults();

    const bvisits = (await cb).visits;
    bvisits.sort((f, s) => (s.time - f.time));
    // TODO ugh, should do it via sort predicate...
    const with_ctx = [];
    const no_ctx = [];
    for (const v of bvisits) {
        if (v.context === null) {
            no_ctx.push(v);
        } else {
            with_ctx.push(v);
        }
    }
    // TODO duplicated code...
    const visits = [].concat(with_ctx).concat(no_ctx);


    const res = getResultsContainer();
    const cc = doc.createElement('div'); res.appendChild(cc);
    cc.classList.add('summary');
    const node = doc.createTextNode(`Found ${visits.length} visits`); cc.appendChild(node);


    const binder = new Binder(doc);
    // TODO use something more generic for that!
    for (const v of visits) {
        const [dates, times] = _fmt(v.time)
        binder.render(res, dates, times, v.tags, {
            timestamp     : v.time,
            original_url  : v.original_url,
            normalised_url: v.normalised_url,
            context       : v.context,
            locator       : v.locator,
        });
        // const el = doc.createElement('div'); res.appendChild(el);
        // const node = document.createTextNode(JSON.stringify(visit)); el.appendChild(node);
    }
}

async function doSearch (cb: Promise<Visits>) {
    try {
        await _doSearch(cb);
    } catch (err) {
        console.error(err);
        try {
            showError(err);
        } catch (err_2) {
            // backup for worst case..
            alert(err_2);
        }
    }
}

unwrap(doc.getElementById('search_id')).addEventListener('submit', async (event) => {
    event.preventDefault();
    await doSearch(searchVisits(getQuery().value));
});


window.onload = async () => {
    const url = new URL(window.location);
    const params = url.searchParams;
    if ([...params.keys()].length == 0) {
        return;
    }

    if (params.has('timestamp')) {
        const timestamp = parseInt(unwrap(params.get('timestamp')));
        await doSearch(searchAround(timestamp));
    }
    // TODO otherwise, error??
};
