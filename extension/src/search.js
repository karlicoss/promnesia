/* @flow */

import {unwrap} from './common';
import type {Visits} from './common';
import {get_options_async} from './options';
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


async function _doSearch(cb: Promise<Visits>, {with_ctx_first, }: {with_ctx_first: boolean}) {
    clearResults();

    const visits = (await cb).visits;
    visits.sort((f, s) => (s.time - f.time));
    // TODO ugh, should do it via sort predicate...

    if (with_ctx_first) {
        visits.sort((f, s) => (f.context === null ? 1 : 0) - (s.context === null ? 1 : 0));
    }

    const res = getResultsContainer();
    const cc = doc.createElement('div'); res.appendChild(cc);
    cc.classList.add('summary');
    // TODO display similar summary as on sidebar?
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

async function doSearch (...args) {
    try {
        await _doSearch(...args);
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
    // TODO make ctx first configurable?
    await doSearch(searchVisits(getQuery().value), {with_ctx_first: true});
});


window.onload = async () => {
    const opts = await get_options_async();
    const style = doc.createElement('style');
    style.innerHTML = opts.extra_css;
    unwrap(doc.head).appendChild(style);

    const url = new URL(window.location);
    const params = url.searchParams;
    if ([...params.keys()].length == 0) {
        return;
    }

    if (params.has('timestamp')) {
        const timestamp = parseInt(unwrap(params.get('timestamp')));
        await doSearch(searchAround(timestamp), {with_ctx_first: false});
    }
    // TODO otherwise, error??
};
