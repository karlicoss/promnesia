/* @flow */

import {unwrap} from './common';
import type {Visits} from './common';
import {searchVisits, searchAround} from './background';
import {Binder, _fmt} from './display';

function getInputElement(element_id: string): HTMLInputElement {
    return ((document.getElementById(element_id): any): HTMLInputElement);
}

function getQuery(): HTMLInputElement {
    return getInputElement('query_id');
}

function getResultsContainer(): HTMLElement {
    return ((document.getElementById('visits'): any): HTMLElement);
}

const doc = document;


async function _doSearch(cb: Promise<Visits>) {
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

    while (res.firstChild) {
        res.removeChild(res.firstChild);
    }
    // TODO FIXME lag before clearing results?

    const binder = new Binder(doc);
    // TODO use something more generic for that!
    for (const v of visits) {
        // TODO need url as well?
        const [dates, times] = _fmt(v.time)
        binder.render(res, dates, times, v.tags, {nurl: v.nurl, context: v.context, locator: v.locator});
        // const el = doc.createElement('div'); res.appendChild(el);
        // const node = document.createTextNode(JSON.stringify(visit)); el.appendChild(node);
    }
}

async function doSearch (cb: Promise<Visits>) {
    try {
        await _doSearch(cb);
    } catch (err) {
        console.error(err);
        alert(err);
    }
}

unwrap(doc.getElementById('search_id')).addEventListener('click', async () => {
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
