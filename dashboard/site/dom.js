// Tiny DOM helpers. All text goes through text nodes (never innerHTML), since
// commit titles and benchmark names come from external data.

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  setAttrs(el, attrs);
  append(el, children);
  return el;
}

const SVG_NS = "http://www.w3.org/2000/svg";

export function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  setAttrs(el, attrs);
  append(el, children);
  return el;
}

function setAttrs(el, attrs) {
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.setAttribute("class", v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
}

function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

export function clear(el) {
  while (el.firstChild) el.removeChild(el.firstChild);
  return el;
}
