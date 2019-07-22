/* @flow */

import {unwrap} from './common';
import {searchVisits} from './background';
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


async function _doSearch() {
    const bvisits = (await searchVisits(getQuery().value)).visits;
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
unwrap(doc.getElementById('search_id')).addEventListener('click', async () => {
    try {
        await _doSearch();
    } catch (err) {
        console.error(err);
        alert(err);
    }
});


