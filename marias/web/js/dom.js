// Small DOM helpers.  User-supplied text only ever reaches the page through
// textContent, never through innerHTML.

export const $ = (selector, root = document) => root.querySelector(selector);

/**
 * Create an element: h('button.primary', { type: 'button', onclick: fn }, 'Text', child)
 */
export function h(spec, props, ...children) {
  const [tag, ...classes] = spec.split('.');
  const element = document.createElement(tag || 'div');
  if (classes.length) element.className = classes.join(' ');
  if (props) {
    for (const [key, value] of Object.entries(props)) {
      if (value === null || value === undefined || value === false) continue;
      if (key.startsWith('on') && typeof value === 'function') {
        element.addEventListener(key.slice(2), value);
      } else if (key === 'class') {
        for (const name of String(value).split(' ')) if (name) element.classList.add(name);
      } else if (key === 'dataset') {
        Object.assign(element.dataset, value);
      } else if (key in element && key !== 'list' && key !== 'form') {
        element[key] = value;
      } else {
        element.setAttribute(key, value === true ? '' : String(value));
      }
    }
  }
  append(element, ...children);
  return element;
}

export function append(parent, ...children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return parent;
}

export function replace(parent, ...children) {
  parent.replaceChildren();
  return append(parent, ...children);
}

let toastTimer = 0;

export function toast(message, kind = 'info') {
  const box = $('#toasts');
  const item = h(`div.toast.${kind}`, null, message);
  box.replaceChildren(item);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => item.remove(), 4500);
}

export function storageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function storageSet(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* private mode: the session simply will not survive a reload */
  }
}
