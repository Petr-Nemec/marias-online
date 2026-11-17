// Card faces drawn as inline SVG.  The artwork is original and deliberately
// simple: one suit mark, an index in two corners, and the traditional cue of
// German-suited packs – the spodek carries its mark low, the svršek high.

export const SUIT_NAMES = { h: 'červené', l: 'zelené', b: 'kule', a: 'žaludy' };
export const SUIT_ADJ = { h: 'červen', l: 'zelen', b: 'kulov', a: 'žaludov' };
export const RANK_NAMES = {
  7: 'sedma', 8: 'osma', 9: 'devítka', X: 'desítka', J: 'spodek', Q: 'svršek', K: 'král', A: 'eso',
};
const RANK_INDEX = { 7: '7', 8: '8', 9: '9', X: '10', J: 'Sp', Q: 'Sv', K: 'K', A: 'A' };
const SUIT_COLOR = { h: '#c0262d', l: '#2c7a3a', b: '#c98f0e', a: '#7d4f24' };

const ORDER_TRUMP = '789JQKXA';
const ORDER_PLAIN = '789XJQKA';
const SUIT_ORDER = 'hlba';

// Suit marks on a 24×24 grid (static markup, no user data).
const SUIT_MARK = {
  h: '<path d="M12 21.2C7.6 18 2.6 14 2.6 8.9 2.6 5.9 4.8 3.8 7.5 3.8c1.9 0 3.5 1 4.5 2.7 1-1.7 2.6-2.7 4.5-2.7 2.7 0 4.9 2.1 4.9 5.1 0 5.1-5 9.1-9.4 12.3z"/>',
  l: '<path d="M12 1.8c4.6 3.4 7.8 7.2 7.8 11.3 0 3.4-2.9 5.6-7 5.9V22.2h-1.6v-3.2c-4.1-.3-7-2.5-7-5.9C4.2 9 7.4 5.200 12 1.8z"/><path d="M12 6.500v10.5" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1" stroke-linecap="round"/>',
  b: '<circle cx="12" cy="12" r="8.6"/><path d="M4.200 13.600h15.600" fill="none" stroke="#fff" stroke-opacity=".7" stroke-width="1.300"/><circle cx="12" cy="17.300" r="1.500" fill="#fff" fill-opacity=".7"/>',
  a: '<path d="M11.200 1.500h1.600v3h-1.600z"/><path d="M4.800 11.200c0-4 3.200-6.700 7.200-6.700s7.200 2.700 7.200 6.700v.9H4.800z"/><path d="M6.300 13.400h11.400c0 4.800-2.500 8-5.700 9.100-3.200-1.100-5.700-4.300-5.700-9.100z" fill-opacity=".72"/>',
};

const CROWN = '<path d="M3 17.500 4.500 7l4.300 4.300L12 5.500l3.200 5.800L19.500 7 21 17.500z"/><rect x="3" y="18.600" width="18" height="2.200" rx=".6"/>';

export const suitOf = (card) => card[0];
export const rankOf = (card) => card[1];

export function cardName(card) {
  const adj = SUIT_ADJ[card[0]];
  const rank = RANK_NAMES[card[1]];
  if (card[1] === 'A') return `${adj}é eso`;
  if ('789X'.includes(card[1])) return `${adj}á ${rank}`;
  return `${adj}ý ${rank}`;
}

export function sortCards(cards, { plain = false, trump = null } = {}) {
  const order = plain ? ORDER_PLAIN : ORDER_TRUMP;
  const suitRank = (suit) => (suit === trump ? -1 : SUIT_ORDER.indexOf(suit));
  return [...cards].sort(
    (x, y) => suitRank(x[0]) - suitRank(y[0]) || order.indexOf(y[1]) - order.indexOf(x[1]),
  );
}

function mark(suit, x, y, size) {
  const scale = size / 24;
  return `<g transform="translate(${x} ${y}) scale(${scale})" fill="${SUIT_COLOR[suit]}">${SUIT_MARK[suit]}</g>`;
}

function faceSvg(card) {
  const suit = card[0];
  const rank = card[1];
  const color = SUIT_COLOR[suit];
  const index = RANK_INDEX[rank];
  const corner = (flip) => `
    <g ${flip ? 'transform="rotate(180 30 45)"' : ''}>
      <text x="5" y="15.500" font-size="${index.length > 1 ? 11 : 13.500}" font-weight="700" fill="${color}">${index}</text>
      ${mark(suit, 4.500, 18, 9)}
    </g>`;
  let centre;
  if (rank === 'J') {
    centre = `${mark(suit, 19, 46, 22)}<text x="30" y="40" text-anchor="middle" font-size="7" fill="#5b5346">spodek</text>`;
  } else if (rank === 'Q') {
    centre = `${mark(suit, 19, 22, 22)}<text x="30" y="56" text-anchor="middle" font-size="7" fill="#5b5346">svršek</text>`;
  } else if (rank === 'K') {
    centre = `<g transform="translate(18 20)" fill="${color}">${CROWN}</g>${mark(suit, 20, 45, 20)}`;
  } else if (rank === 'A') {
    centre = mark(suit, 12, 27, 36);
  } else if (rank === 'X') {
    centre = `${mark(suit, 19, 22, 22)}${mark(suit, 19, 46, 22)}`;
  } else {
    centre = `${mark(suit, 17, 30, 26)}`;
  }
  return `<svg viewBox="0 0 60 90" aria-hidden="true" focusable="false">
    <rect x=".75" y=".75" width="58.500" height="88.500" rx="5" fill="#fbf8ef" stroke="#cdc5b1" stroke-width="1.500"/>
    ${corner(false)}${corner(true)}${centre}</svg>`;
}

const BACK_SVG = `<svg viewBox="0 0 60 90" aria-hidden="true" focusable="false">
  <rect x=".75" y=".75" width="58.500" height="88.500" rx="5" fill="#7b2231" stroke="#4f1420" stroke-width="1.500"/>
  <rect x="5" y="5" width="50" height="80" rx="3" fill="none" stroke="#e7c887" stroke-opacity=".7" stroke-width="1"/>
  <path d="M30 14 46 45 30 76 14 45z" fill="none" stroke="#e7c887" stroke-opacity=".55" stroke-width="1"/>
  <path d="M30 28 39 45 30 62 21 45z" fill="#e7c887" fill-opacity=".35"/></svg>`;

const faceCache = new Map();

/** A card element; interactive cards are buttons, the rest plain spans. */
export function cardElement(card, { button = false, small = false } = {}) {
  const element = document.createElement(button ? 'button' : 'span');
  element.className = `card${small ? ' small' : ''}`;
  if (button) element.type = 'button';
  element.dataset.card = card;
  if (!faceCache.has(card)) faceCache.set(card, faceSvg(card));
  element.innerHTML = faceCache.get(card);
  const name = cardName(card);
  element.title = name;
  if (button) element.setAttribute('aria-label', name);
  else element.setAttribute('role', 'img'), element.setAttribute('aria-label', name);
  return element;
}

export function cardBack({ small = false } = {}) {
  const element = document.createElement('span');
  element.className = `card back${small ? ' small' : ''}`;
  element.innerHTML = BACK_SVG;
  return element;
}

/** Inline suit mark with its Czech name, e.g. for the contract banner. */
export function suitBadge(suit) {
  const element = document.createElement('span');
  element.className = 'suit';
  element.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><g fill="${SUIT_COLOR[suit]}">${SUIT_MARK[suit]}</g></svg>`;
  element.append(SUIT_NAMES[suit]);
  return element;
}
