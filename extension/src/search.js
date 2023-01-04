/* @flow */

import {unwrap, addStyle, chunkBy, Ids} from './common'
import type {Visits, Visit, SearchPageParams} from './common'
import {getOptions} from './options'
import {Binder, _fmt} from './display'
import {allsources} from './sources'


const doc = document;

function getInputElement(element_id: string): HTMLInputElement {
    return ((doc.getElementById(element_id): any): HTMLInputElement);
}

function getQuery(): HTMLInputElement {
    return getInputElement('query_id');
}

function getResultsContainer(): HTMLElement {
    return ((doc.getElementById(Ids.VISITS): any): HTMLElement);
}


function clearResults() {
    const res = getResultsContainer();
    while (res.firstChild) {
        res.removeChild(res.firstChild);
    }
}


// TODO reuse it in sidebar??
function showError(err: Error): void {
    clearResults();
    const res = getResultsContainer();
    const err_c = doc.createElement('div'); res.appendChild(err_c);
    err_c.classList.add('error');
    const err_text = doc.createTextNode(err.toString()); err_c.appendChild(err_text);
}


async function* _doSearch(
    cb: Promise<Visits | Error>,
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

    const errres = await cb
    if (errres instanceof Error) {
        throw errres // will be handled above
    }
    const [visits, errors] = errres.partition()
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


    const options = await getOptions()
    const binder = new Binder(doc, options)
    // TODO use something more generic for that!

    for (const err of errors) {
        await binder.renderError(res, err)
    }

    const ONE_CHUNK = 250
    for (const chunk of chunkBy(visits, ONE_CHUNK)) {
    yield // give way to UI thread
    for (const v of chunk) {
        const [dates, times] = _fmt(v.time)
        const cc = await binder.render(res, dates, times, v.tags, {
            idx           : null,
            timestamp     : v.time,
            original_url  : v.original_url,
            normalised_url: v.normalised_url,
            context       : v.context,
            locator       : v.locator,
            relative      : false,
        });
        // hmm flow seems a bit dumb here
        // $FlowFixMe[not-a-function]
        if (highlight_if(v)) {
            cc.classList.add('highlight');
        }
    }
    }
}


function showOrAlert(err: Error): void {
    try {
        showError(err)
    } catch (e2) {
        console.error(e2)
        alert(e2) // last resort
    }
}

// $FlowFixMe[missing-local-annot]
async function doSearch(...args) {
    const dom_updates = _doSearch(...args)
    async function consume_one() {
        // consume head
        let res = null
        try {
            res = await dom_updates.next()
        } catch (err) {
            console.error(err)
            showOrAlert(err)
        }
        if (res == null) {
            // early exit because of the error
            return
        }
        if (!res.done) {
            // schedule tail
            setTimeout(consume_one)
        }
    }
    await consume_one()
}


unwrap(doc.getElementById('search_id')).addEventListener('submit', async (event: Event) => {
    event.preventDefault();
    const url = new URL(window.location)
    url.searchParams.set('q', getQuery().value)
    window.history.pushState({}, '', url)
    // TODO make ctx first configurable?
    await doSearch(
        allsources.search(getQuery().value),
        {
            with_ctx_first: true,
            highlight_if: null,
        },
    );
});


window.onload = async () => {
    const opts = await getOptions()
    addStyle(doc, opts.position_css);

    const url = new URL(window.location)
    const params: SearchPageParams = Object.fromEntries(url.searchParams)
    if (Object.keys(params).length == 0) {
        return
    }

    const q_param = params['q']
    if (q_param != null) {
        getQuery().value = q_param
        await doSearch(
            allsources.search(getQuery().value),
            {
                with_ctx_first: true,
                highlight_if: null,
            },
        )
        return
    }

    // todo need to be better tested, with various timezones etc
    const ts_param = params['utc_timestamp_s']
    if (ts_param != null) {
        const timestamp = parseInt(unwrap(ts_param));
        await doSearch(
            allsources.searchAround(timestamp),
            {
                with_ctx_first: false,
                // todo eh, need some proper handles here, e.g. some visit id...
                highlight_if: (v: Visit) => Math.floor(v.time.getTime() / 1000) == timestamp,
            },
        )
        return
    }
    // TODO otherwise, error??
};
