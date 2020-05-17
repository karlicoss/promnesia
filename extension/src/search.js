/* @flow */

import {unwrap, addStyle} from './common';
import type {Visits, Visit} from './common';
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


// TODO reuse it in sidebar??
function showError(err) {
    clearResults();
    const res = getResultsContainer();
    const err_c = doc.createElement('div'); res.appendChild(err_c);
    err_c.classList.add('error');
    const err_text = doc.createTextNode(err); err_c.appendChild(err_text);
}


async function _doSearch(
    cb: Promise<Visits>,
    {
        with_ctx_first,
        highlight_if,
    }: {
        with_ctx_first: boolean,
        highlight_if: ?((Visit) => boolean),
    }
) {
    if (highlight_if == null) {
        // eslint-disable-next-line no-unused-vars
        highlight_if = (_) => false;
    }

    clearResults();

    const visits = (await cb).visits;
    visits.sort((f, s) => (s.time - f.time));
    // TODO ugh, should do it via sort predicate...

    if (with_ctx_first) {
        visits.sort((f, s) => (f.context === null ? 1 : 0) - (s.context === null ? 1 : 0));
    }

    // TODO res is undefined??
    const res = getResultsContainer();
    const cc = doc.createElement('div'); res.appendChild(cc);
    cc.classList.add('summary');
    // TODO display similar summary as on sidebar?
    const node = doc.createTextNode(`Found ${visits.length} visits`); cc.appendChild(node);


    const binder = new Binder(doc);
    // TODO use something more generic for that!
    for (const v of visits) {
        const [dates, times] = _fmt(v.time)
        const cc = binder.render(res, dates, times, v.tags, {
            idx           : null,
            timestamp     : v.time,
            original_url  : v.original_url,
            normalised_url: v.normalised_url,
            context       : v.context,
            locator       : v.locator,
            relative      : false,
        });
        if (highlight_if(v)) {
            cc.classList.add('highlight');
        }
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

unwrap(doc.getElementById('search_id')).addEventListener('submit', async (event: Event) => {
    event.preventDefault();
    // TODO make ctx first configurable?
    await doSearch(
        searchVisits(getQuery().value),
        {
            with_ctx_first: true,
            highlight_if: null,
        },
    );
});


window.onload = async () => {
    const opts = await get_options_async();
    addStyle(doc, opts.position_css);

    const url = new URL(window.location);
    const params = url.searchParams;
    if ([...params.keys()].length == 0) {
        return;
    }

    // todo need to be better tested, with various timezones etc
    const ts_param = params.get('utc_timestamp');
    if (ts_param != null) {
        const timestamp = parseInt(unwrap(ts_param));
        await doSearch(
            searchAround(timestamp),
            {
                with_ctx_first: false,
                // TODO duplication..
                highlight_if: (v: Visit) => v.time.getTime() / 1000 == timestamp,
            },
        );
    }
    // TODO otherwise, error??
};
