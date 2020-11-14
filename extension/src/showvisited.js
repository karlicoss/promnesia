/* NOTE: this file is kept intact by webpack, for the sake of highlighting and linting  */

// 'API': take
// - link_element: list of <a> DOM elements on the page
// - visited: Map<Url, ?Visit>
// then you can walk through this and decorate as you please

function addStyle(css) {
    const style = document.createElement('style')
    style.appendChild(document.createTextNode(css))
    document.head.appendChild(style)
}


addStyle(`
.promnesia-visited:after {
  content: "⚫";
  color: #FF4500;
  vertical-align: super;
  font-size: smaller;

  /* prevent selecting along with the text */
  user-select: none;

  position:absolute;
  z-index:100;
}
`)


function formatVisit(v) {
    const e = document.createElement('code')
    e.style.whiteSpace = 'pre'
    e.style.display = 'block'
    const {original_url: original, dt_local: dt, tags: tags, context: context, locator: locator} = v
    e.textContent = `
original: ${original}
dt      : ${dt}
tags    : ${tags.join(' ')}
context : ${(context || '').trim()}
`.trim()
    const els = [e]
    const {href: href, title: title} = locator || {}
    if (href != null) {
        const a = document.createElement('a')
        a.title = title
        a.href  = href
        a.appendChild(document.createTextNode(title))
        els.push(a)
    }
    return els
}

// TODO I guess, these snippets could be writable by people? and then they can customize tooltips to their liking
// returns extra elements to insert in DOM
function decorateLink(element) {
    const url = element.href
    // 'visited' passed in backgroud.js
    // eslint-disable-next-line no-undef
    const v = visited.get(url)
    if (!v) {
        return // no visits
    }

    element.classList.add('promnesia-visited')
    if (v === true) {
        // nothing else interesting we can do with such visit
        return
    }

    let popup = document.createElement('div')
    let toggler  = document.createElement('span')
    popup.appendChild(toggler)
    toggler.textContent = '⚫⚫⚫' // TODO decorate url as well??
    toggler.classList.add('nonselectable')

    let content = document.createElement('div')
    content.style.border = 'solid 1px'
    content.style.background = 'lightyellow'
    content.visibility = 'hidden'
    popup.appendChild(content)
    // TODO max width??
    // TODO use an actual style or something?
    let ev = formatVisit(v)
    for (const e of ev) {
        content.appendChild(e)
    }


    // TODO would be cool to reuse the same style used by the sidebar...
    let rect = element.getBoundingClientRect()
    for (const [e, y] of [[toggler, 0], [content, 20]]) {
        e.style.top  = (window.scrollY + rect.top + y).toString() + 'px'
        e.style.left = (window.scrollX + rect.right  ).toString() + 'px'
        e.style.position = 'absolute'
    }
    // logic as follows: when over toggler, show the popup
    const over = () => {
       content.classList.remove('nonselectable')
       content.style.display = 'block'
       toggler.style.opacity = 1

       toggler.removeEventListener('mouseover', over)
       toggler.addEventListener   ('mouseout' , out )
    }
    // when out toggler, hide it
    const out = () => {
       content.classList.add('nonselectable')
       content.style.display = 'none'
       toggler.style.opacity = 0.1

       toggler.removeEventListener('mouseout' , out )
       toggler.addEventListener   ('mouseover', over)
    }
    // and click to pin/unpin!
    const click = () => {
       const pinned = content.pinned || false
       if (pinned) {
           over() // let default behaviour take over
       } else {
           toggler.removeEventListener('mouseout' , out)
           toggler.removeEventListener('mouseover', over)
       }
       content.pinned = !pinned
    }
    toggler.addEventListener('click', click)
    out()
    element.appendChild(popup)
    return [popup]
}

function decorateLinks() {
    let cont = document.createElement('div') // todo class?
    document.body.appendChild(cont)

    // 'link_elements' passed in backgroud.js
    // eslint-disable-next-line no-undef
    for (const link_element of link_elements) {
        let elems = null
        try { // best to be defensive here..
            elems = decorateLink(link_element)
        } catch (e) {
            console.error(e)
        }

        if (elems != null) {
            for (const e of elems) {
                cont.appendChild(e)
            }
        }

    }
}

decorateLinks()
