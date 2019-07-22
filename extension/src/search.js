/* @flow */

import {unwrap, Blacklisted} from './common';
import {getVisits} from './background';

function getInputElement(element_id: string): HTMLInputElement {
    return ((document.getElementById(element_id): any): HTMLInputElement);
}

function getQuery(): HTMLInputElement {
    return getInputElement('query_id');
}

function getResultsContainer(): HTMLElement {
    return ((document.getElementById('results_id'): any): HTMLElement);
}

const doc = document;

// doc.addEventListener('DOMContentLoaded', async () => {
//     // TODO ??
// });


unwrap(doc.getElementById('search_id')).addEventListener('click', async () => {
    // TODO query shouldn't go through blacklisting...
    const visits = await getVisits(getQuery().value);
    // TODO FIXME send proper query to serve
    console.log(visits);

    const res = getResultsContainer();

    while (res.firstChild) {
        res.removeChild(res.firstChild);
    }

    // TODO use something more generic for that!
    if (visits instanceof Blacklisted) {
        throw "shouldn't happen!";
    }
    for (const visit of visits.visits) {
        const el = doc.createElement('div'); res.appendChild(el);
        const node = document.createTextNode(JSON.stringify(visit)); el.appendChild(node);
    }
});


