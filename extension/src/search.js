/* @flow */

import {unwrap} from './common';
import {searchVisits} from './background';

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

unwrap(doc.getElementById('search_id')).addEventListener('click', async () => {
    const visits = await searchVisits(getQuery().value);
    console.log(visits);

    const res = getResultsContainer();

    while (res.firstChild) {
        res.removeChild(res.firstChild);
    }

    // TODO use something more generic for that!
    for (const visit of visits.visits) {
        const el = doc.createElement('div'); res.appendChild(el);
        const node = document.createTextNode(JSON.stringify(visit)); el.appendChild(node);
    }
});


