// The table view: seats, trick, hand, actions, log and score sheet.
//
// The server sends a complete snapshot after every change; this view renders
// it and keeps only presentation state of its own (what is selected, which
// tab is open, how long a finished trick stays on the table).

import { cardBack, cardElement, cardName, sortCards, suitBadge } from './cards.js';
import { $, append, h, replace, storageGet, storageSet, toast } from './dom.js';
import { CONTRACT_TYPES, FLEK_WORDS, PART_ACC, PART_NAMES, amount, clock, money, plural } from './format.js';
import { play as playSound } from './sound.js';

const LADDER = {
  sedma: [1, 2], sto: [3, 5], sto_sedma: [4, 6], betl: [7, 7], durch: [8, 8],
  dve_sedmy: [9, 11], dve_sedmy_sto: [10, 12],
};
const LEVEL_NAMES = [
  '', 'Sedma', 'Sedma červená', 'Sto', 'Sto a sedma', 'Sto červených', 'Sto a sedma červených',
  'Betl', 'Durch', 'Dvě sedmy', 'Dvě sedmy a sto', 'Dvě sedmy, červená trumf',
  'Dvě sedmy, červená trumf, a sto',
];
const SUITS = ['h', 'l', 'b', 'a'];
const TRICK_HOLD_MS = 1600;
const BUBBLE_MS = 3200;
const BUBBLE_EVENTS = new Set(['bid', 'hold', 'pass', 'flek', 'omyl']);
const AUTO_KEY = 'marias.autoAnnounce';

export class TableView {
  constructor(root, { send, leave }) {
    this.root = root;
    this.sendMessage = send;
    this.leaveTable = leave;
    this.player = null;
    this.state = null;
    this.lastSeq = 0;
    this.bubbles = new Map();
    this.holdUntil = 0;
    this.deadline = null;
    this.ui = this.#freshUi();
    this.autoAnnounce = storageGet(AUTO_KEY) !== 'off';
    this.#build();
    setInterval(() => this.#tickClock(), 250);
  }

  #freshUi() {
    return {
      deal: 0, discards: new Set(), type: null, trump: null, helper: null,
      showLast: false, reveal: false, pendingCard: null, tab: 'log', sideOpen: false,
    };
  }

  setPlayer(player) {
    this.player = player;
  }

  reset() {
    this.state = null;
    this.lastSeq = 0;
    this.bubbles.clear();
    this.ui = this.#freshUi();
    replace(this.logList);
  }

  // ------------------------------------------------------------------- layout

  #build() {
    this.title = h('div.table-title');
    this.lastButton = h('button.ghost', { type: 'button', onclick: () => this.#toggle('showLast') }, 'Poslední štych');
    this.sideButton = h('button.ghost.side-toggle', { type: 'button', onclick: () => this.#toggle('sideOpen') }, 'Záznam a lístek');
    const top = h(
      'div.table-top',
      null,
      this.title,
      h(
        'div.table-top-actions',
        null,
        this.lastButton,
        h('button.ghost', { type: 'button', onclick: () => this.#invite() }, 'Pozvat hráče'),
        this.sideButton,
        h('button.ghost', { type: 'button', onclick: () => this.#confirmLeave() }, 'Odejít od stolu'),
      ),
    );
    this.opponents = h('div.opponents');
    this.contract = h('div.contract');
    this.trick = h('div.trick');
    this.overlay = h('div.overlay', { hidden: true });
    this.actions = h('div.actions');
    this.mePlate = h('div.me-plate');
    this.hand = h('div.hand');
    const felt = h(
      'div.felt',
      null,
      top,
      this.opponents,
      (this.centre = h('div.centre', null, this.contract, this.trick, this.overlay)),
      this.actions,
      h('div.me', null, this.mePlate, this.hand),
    );

    this.tabLog = h('button', { type: 'button', role: 'tab', onclick: () => this.#setTab('log') }, 'Záznam');
    this.tabSheet = h('button', { type: 'button', role: 'tab', onclick: () => this.#setTab('sheet') }, 'Lístek');
    this.logList = h('ol.log', { 'aria-live': 'polite' });
    this.sheet = h('div.sheet', { hidden: true });
    this.chatInput = h('input', { type: 'text', maxLength: 200, placeholder: 'Napiš zprávu ke stolu', 'aria-label': 'Zpráva ke stolu', autocomplete: 'off' });
    const chat = h(
      'form.chat',
      {
        onsubmit: (event) => {
          event.preventDefault();
          const text = this.chatInput.value.trim();
          if (!text) return;
          this.sendMessage({ type: 'chat', text });
          this.chatInput.value = '';
        },
      },
      this.chatInput,
      h('button.primary', { type: 'submit' }, 'Odeslat'),
    );
    this.side = h(
      'aside.side',
      null,
      h('div.tabs', { role: 'tablist' }, this.tabLog, this.tabSheet,
        h('button.ghost.side-close', { type: 'button', onclick: () => this.#toggle('sideOpen') }, 'Zavřít')),
      this.logList,
      this.sheet,
      chat,
    );
    replace(this.root, felt, this.side);
  }

  #toggle(key) {
    this.ui[key] = !this.ui[key];
    this.#render();
  }

  #setTab(tab) {
    this.ui.tab = tab;
    this.#render();
  }

  // ------------------------------------------------------------------ updates

  update(state) {
    const previous = this.state;
    this.state = state;
    const deal = state.deal;

    if (this.ui.deal !== state.deal_number) {
      const keep = { tab: this.ui.tab, sideOpen: this.ui.sideOpen };
      this.ui = { ...this.#freshUi(), ...keep, deal: state.deal_number };
    }
    if (!deal || deal.phase !== 'talon') {
      this.ui.discards.clear();
    }
    if (!deal || deal.phase !== 'done') this.ui.reveal = false;

    // A trick that has just been completed stays on the table for a moment.
    const tricksBefore = previous?.deal && previous.deal_number === state.deal_number
      ? previous.deal.tricks_won.reduce((a, b) => a + b, 0) : 0;
    const tricksNow = deal ? deal.tricks_won.reduce((a, b) => a + b, 0) : 0;
    if (deal && tricksNow > tricksBefore && previous) {
      this.holdUntil = performance.now() + TRICK_HOLD_MS;
      setTimeout(() => this.#render(), TRICK_HOLD_MS + 30);
    }

    this.deadline = state.remaining_ms === null ? null : performance.now() + state.remaining_ms;
    this.#absorbLog(state, previous);

    const mine = state.you.seat !== null && state.turn_seat === state.you.seat;
    const wasMine = previous && previous.you.seat !== null && previous.turn_seat === previous.you.seat
      && previous.deal_number === state.deal_number && previous.deal?.phase === deal?.phase
      && previous.deal?.trick_number === deal?.trick_number;
    if (mine && !wasMine) playSound('turn');
    if (deal?.phase === 'done' && previous?.deal && previous.deal.phase !== 'done') playSound('done');

    this.#render();
  }

  #absorbLog(state, previous) {
    const fresh = state.log.filter((entry) => entry.seq > this.lastSeq);
    if (!fresh.length) return;
    const initial = this.lastSeq === 0 && !previous;
    const stick = this.logList.scrollHeight - this.logList.scrollTop - this.logList.clientHeight < 60;
    for (const entry of fresh) {
      this.lastSeq = entry.seq;
      const item = h(`li.${entry.kind}`, null);
      if (entry.kind === 'chat') {
        item.append(h('span.time', null, clock(entry.ts)), h('b', null, `${entry.name}: `), entry.text);
      } else {
        item.append(entry.text);
      }
      this.logList.append(item);
      if (!initial && entry.kind === 'game') {
        if (entry.ev === 'play') playSound('card');
        if (BUBBLE_EVENTS.has(entry.ev) && entry.seat !== null && entry.seat !== undefined) {
          const text = entry.text.includes(': ') ? entry.text.slice(entry.text.indexOf(': ') + 2) : entry.text;
          this.bubbles.set(entry.seat, { text, until: performance.now() + BUBBLE_MS });
          setTimeout(() => this.#render(), BUBBLE_MS + 30);
        }
      }
    }
    while (this.logList.children.length > 250) this.logList.firstChild.remove();
    if (stick || initial) this.logList.scrollTop = this.logList.scrollHeight;
  }

  #tickClock() {
    if (!this.state || this.root.hidden) return;
    const left = this.deadline === null ? null : Math.max(0, this.deadline - performance.now());
    for (const bar of this.root.querySelectorAll('.timer > i')) {
      const total = Number(bar.dataset.total) || 1;
      bar.style.setProperty('width', left === null ? '0%' : `${Math.min(100, (left / total) * 100)}%`);
    }
    const countdown = $('.countdown', this.root);
    if (countdown) countdown.textContent = left === null ? '' : `${Math.ceil(left / 1000)} s`;
  }

  // ---------------------------------------------------------------- shortcuts

  get mySeat() {
    return this.state.you.seat;
  }

  get viewSeat() {
    return this.state.you.seat ?? 0;
  }

  #seatName(index) {
    return this.state.seats[index]?.name || 'volné místo';
  }

  #roleName(role) {
    return this.#seatName(this.state.deal.role_seats[role]);
  }

  #act(action) {
    this.sendMessage({ type: 'action', action });
  }

  /** Seats other than the viewer's, clockwise, with their position on screen. */
  #others() {
    const count = this.state.seats.length;
    const positions = count === 3 ? ['left', 'right'] : ['left', 'top', 'right'];
    return positions.map((position, i) => ({
      position,
      seat: this.state.seats[(this.viewSeat + i + 1) % count],
    }));
  }

  #positionOf(seatIndex) {
    if (seatIndex === this.viewSeat) return 'bottom';
    return this.#others().find((o) => o.seat.index === seatIndex)?.position ?? 'top';
  }

  // ------------------------------------------------------------------- render

  #render() {
    const state = this.state;
    if (!state) return;
    const stake = state.options.stake;
    replace(
      this.title,
      h('h1', null, state.options.name),
      h(
        'p',
        null,
        `základ ${money(1, stake)}`,
        state.deal_number ? `, ${state.deal_number}. hra` : '',
        state.options.private ? ', soukromý stůl' : '',
        state.you.spectator ? ' – díváš se' : '',
      ),
    );
    this.lastButton.hidden = !state.deal?.last_trick || state.deal.phase !== 'play';
    this.lastButton.setAttribute('aria-pressed', String(this.ui.showLast));

    replace(this.opponents, this.#others().map(({ seat, position }) => this.#plate(seat, position)));
    this.opponents.dataset.count = String(state.seats.length - 1);
    replace(this.mePlate, this.#plate(state.seats[this.viewSeat], 'bottom'));

    this.#renderContract();
    this.#renderTrick();
    this.#renderOverlay();
    this.#renderActions();
    this.#renderHand();
    this.#renderSide();
    this.#tickClock();
  }

  #plate(seat, position) {
    const state = this.state;
    const deal = state.deal;
    const playing = state.status === 'playing' && deal;
    const seated = state.you.seat !== null;

    if (!seat.occupied) {
      return h(
        `div.plate.empty.${position}`,
        null,
        h('div.plate-name', null, 'Volné místo'),
        state.you.spectator && state.status !== 'playing'
          ? h('button.primary', { type: 'button', onclick: () => this.sendMessage({ type: 'join_table', table: state.id, seat: seat.index, ...(state.code ? { code: state.code } : {}) }) }, 'Přisednout')
          : null,
        seated
          ? h('button.ghost', { type: 'button', onclick: () => this.sendMessage({ type: 'add_bot', seat: seat.index }) }, 'Posadit počítač')
          : null,
      );
    }

    const badges = [];
    let role = null;
    if (deal) role = deal.role_seats.indexOf(seat.index);
    if (deal && state.status !== 'waiting') {
      if (deal.declarer !== null && deal.role_seats[deal.declarer] === seat.index) badges.push(['aktér', 'declarer']);
      if (role === 0) badges.push(['forhont', '']);
      if (state.dealer === seat.index) badges.push([state.seats.length === 4 ? 'rozdával, pauzíruje' : 'rozdával', '']);
    }
    if (!seat.connected) badges.push(['odpojen', 'warn']);
    else if (seat.away) badges.push(['hraje za něj počítač', 'warn']);
    if (state.status !== 'playing' && seat.ready && !seat.bot) badges.push(['připraven', 'ok']);

    const onTurn = state.turn_seat === seat.index;
    const bubble = this.bubbles.get(seat.index);
    const showBubble = state.status === 'playing' && bubble && bubble.until > performance.now();
    const total = state.options.turn_seconds * 1000;

    const meta = [money(seat.money, state.options.stake, { sign: true })];
    if (seat.pb) meta.push(`${seat.pb} PB`);

    let cards = null;
    const ownHand = position === 'bottom' && seat.index === this.mySeat;
    if (playing && role !== null && role >= 0 && !ownHand) {
      const count = deal.hand_counts[role];
      cards = h(
        'div.plate-cards',
        { title: `${plural(count, 'karta', 'karty', 'karet')} v ruce` },
        cardBack({ small: true }),
        h('span', null, `× ${count}`, h('span.sr-only', null, ` ${plural(count, 'karta', 'karty', 'karet')}`)),
        deal.phase === 'play' ? h('span.muted', null, `štychy ${deal.tricks_won[role]}`) : null,
      );
    } else if (playing && role !== null && role >= 0 && deal.phase === 'play') {
      cards = h('div.plate-cards', null, h('span.muted', null, `štychy ${deal.tricks_won[role]}`));
    }

    return h(
      `div.plate.${position}`,
      { class: `${onTurn ? 'turn' : ''} ${seat.connected ? '' : 'offline'}` },
      showBubble ? h('div.bubble', null, bubble.text) : null,
      h('div.plate-name', null, seat.name, seat.index === this.mySeat ? h('span.you', null, ' (ty)') : null),
      badges.length ? h('div.badges', null, badges.map(([text, kind]) => h(`span.badge.${kind || 'plain'}`, null, text))) : null,
      h('div.plate-meta', null, meta.join(', ')),
      cards,
      onTurn && total && !seat.bot ? h('div.timer', null, h('i', { dataset: { total: String(total) } })) : null,
      seat.bot && seated && state.status !== 'playing'
        ? h('button.ghost.tiny', { type: 'button', onclick: () => this.sendMessage({ type: 'remove_bot', seat: seat.index }) }, 'Odebrat počítač')
        : null,
    );
  }

  #renderContract() {
    const deal = this.state.deal;
    if (!deal || this.state.status === 'waiting') {
      replace(this.contract);
      return;
    }
    const parts = [];
    if (deal.phase === 'bidding') {
      parts.push(h('strong', null, 'Licitace'));
      parts.push(deal.bidding.level ? `nabídnuto: ${LEVEL_NAMES[deal.bidding.level]}` : 'zatím bez nabídky');
    } else if (deal.phase === 'talon') {
      parts.push(h('strong', null, `${this.#roleName(deal.declarer)} bere talon`));
      parts.push(deal.forced ? 'nikdo nelicitoval, hraje forhont' : `vylicitováno: ${LEVEL_NAMES[deal.min_level]}`);
    } else if (deal.contract) {
      parts.push(h('strong', null, deal.contract.name));
      parts.push(`hraje ${this.#roleName(deal.declarer)}`);
      if (deal.contract.trump) parts.push(h('span', null, 'trumfy ', suitBadge(deal.contract.trump)));
      if (deal.contract.helper) parts.push(h('span', null, 'pomocná ', suitBadge(deal.contract.helper)));
      for (const [part, count] of Object.entries(deal.flek.counts)) {
        if (count > 0) parts.push(h('span.flek-chip', null, `${PART_NAMES[part]}: ${FLEK_WORDS[count - 1]}`));
      }
    } else if (deal.result) {
      parts.push(h('strong', null, 'Omyl'));
      parts.push(`${this.#roleName(deal.declarer)} složil karty`);
    }
    replace(this.contract, parts.map((part) => h('span.contract-item', null, part)));
  }

  #renderTrick() {
    const deal = this.state.deal;
    replace(this.trick);
    this.trick.classList.remove('past');
    if (!deal || this.state.status === 'waiting') return;
    let cards = deal.trick;
    let winner = null;
    const holding = performance.now() < this.holdUntil;
    const wantLast = this.ui.showLast && deal.phase === 'play';
    if (deal.last_trick && (wantLast || ((holding || deal.phase === 'done') && !cards.length))) {
      cards = deal.last_trick.cards;
      winner = deal.last_trick.winner;
      if (wantLast) this.trick.classList.add('past');
    }
    for (const { p, c } of cards) {
      const seatIndex = deal.role_seats[p];
      const slot = h(`div.slot.${this.#positionOf(seatIndex)}`, { class: winner === p ? 'winner' : '' }, cardElement(c));
      this.trick.append(slot);
    }
    if (wantLast) this.trick.append(h('p.trick-note', null, `Poslední štych vzal ${this.#roleName(winner)}.`));
  }

  // ------------------------------------------------------------------ actions

  #renderActions() {
    const state = this.state;
    const deal = state.deal;
    replace(this.actions);
    if (state.status !== 'playing' || !deal) return;
    const options = deal.options;
    const me = state.seats[this.viewSeat];

    if (me.away && state.you.seat !== null) {
      append(
        this.actions,
        h('p', null, 'Dlouho jsi nehrál, tahy za tebe dělá počítač.'),
        h('button.primary', { type: 'button', onclick: () => this.sendMessage({ type: 'back' }) }, 'Hraju zase sám'),
      );
      return;
    }
    if (!options) {
      const turn = state.turn_seat === null ? '' : `Na tahu je ${this.#seatName(state.turn_seat)}.`;
      append(this.actions, h('p.waiting', null, turn));
      return;
    }
    if (options.kind === 'bid') this.#bidActions(options);
    else if (options.kind === 'talon') this.#talonActions(options);
    else if (options.kind === 'flek') this.#flekActions(options);
    else if (options.kind === 'play') this.#playActions(options);
  }

  #bidActions(options) {
    const deal = this.state.deal;
    if (options.role === 'answer') {
      append(
        this.actions,
        h('p', null, `${this.#roleName(deal.bidding.asker)} nabízí: ${LEVEL_NAMES[options.level]}. Máš přednost – stačí držet.`),
        h('div.buttons', null,
          h('button.primary', { type: 'button', onclick: () => this.#act({ a: 'hold' }) }, 'Mám'),
          h('button.ghost', { type: 'button', onclick: () => this.#act({ a: 'pass' }) }, 'Pas')),
      );
      return;
    }
    const levels = [];
    if (options.can_bid) {
      for (let level = options.min_level; level <= options.max_level; level += 1) levels.push(level);
    }
    append(
        this.actions,
      h('p', null, `Licituješ proti hráči ${this.#roleName(deal.bidding.holder)}. Nabídni stupeň, nebo pasuj.`),
      h('div.buttons.wrap', null,
        levels.map((level, i) => h(`button.${i === 0 ? 'primary' : 'ghost'}`, { type: 'button', onclick: () => this.#act({ a: 'bid', level }) }, LEVEL_NAMES[level])),
        h('button.ghost.pass', { type: 'button', onclick: () => this.#act({ a: 'pass' }) }, 'Pas')),
    );
  }

  #chosenLevel() {
    const { type, trump } = this.ui;
    if (!type) return 0;
    const spec = CONTRACT_TYPES.find((c) => c.type === type);
    if (!spec.trump) return LADDER[type][0];
    if (!trump) return 0;
    return LADDER[type][trump === 'h' ? 1 : 0];
  }

  #talonProblem(options) {
    const { type, trump, helper, discards } = this.ui;
    if (!type) return 'Vyber závazek.';
    const spec = CONTRACT_TYPES.find((c) => c.type === type);
    if (spec.trump && !trump) return 'Vyber trumfy.';
    if (spec.helper && !helper) return 'Vyber pomocnou barvu.';
    const level = this.#chosenLevel();
    if (level < options.min_level) return `Musíš ohlásit aspoň: ${LEVEL_NAMES[options.min_level]}.`;
    if (discards.size !== 2) return 'Vyber v ruce dvě karty do talonu.';
    const hand = this.state.deal.hand;
    if (type === 'sedma' && !hand.includes(`${trump}7`)) return 'Sedmu nelze hrát bez trumfové sedmy v ruce.';
    for (const card of discards) {
      if (spec.trump && 'AX'.includes(card[1])) return 'Esa a desítky smí do talonu jen při betlu a durchu.';
      if (spec.trump && card[1] === '7' && type !== 'sto' && (card[0] === trump || (spec.helper && card[0] === helper))) {
        return 'Hlášenou sedmu nelze odložit do talonu.';
      }
    }
    return null;
  }

  #talonActions(options) {
    const ui = this.ui;
    const spec = CONTRACT_TYPES.find((c) => c.type === ui.type);
    const pick = (key, value) => {
      ui[key] = value;
      if (key === 'type') {
        const next = CONTRACT_TYPES.find((c) => c.type === value);
        if (!next.trump) ui.trump = null;
        if (!next.helper) ui.helper = null;
      }
      if (ui.helper === ui.trump) ui.helper = null;
      this.#render();
    };
    const typeButtons = CONTRACT_TYPES.map((c) => h(
      'button.choice',
      { type: 'button', disabled: LADDER[c.type][1] < options.min_level, 'aria-pressed': String(ui.type === c.type), onclick: () => pick('type', c.type) },
      c.label,
    ));
    const suitButtons = (key, exclude) => SUITS.filter((s) => s !== exclude).map((suit) => h(
      'button.choice',
      { type: 'button', 'aria-pressed': String(ui[key] === suit), onclick: () => pick(key, suit) },
      suitBadge(suit),
    ));
    const problem = this.#talonProblem(options);
    const level = this.#chosenLevel();
    const talonNames = options.talon.map(cardName).join(' a ');

    append(
        this.actions,
      h('p', null,
        options.forced ? 'Nikdo nelicitoval, hrát musíš ty – nejméně sedmu. ' : `Vylicitováno: ${LEVEL_NAMES[options.min_level]}. `,
        `V talonu byly ${talonNames}. Vyber závazek a klepni v ruce na dvě karty, které odložíš.`),
      h('div.picker', null, h('span.picker-label', null, 'Závazek'), h('div.buttons.wrap', null, typeButtons)),
      spec?.trump ? h('div.picker', null, h('span.picker-label', null, 'Trumfy'), h('div.buttons.wrap', null, suitButtons('trump', null))) : null,
      spec?.helper ? h('div.picker', null, h('span.picker-label', null, 'Pomocná'), h('div.buttons.wrap', null, suitButtons('helper', ui.trump))) : null,
      h('div.buttons', null,
        h('button.primary', {
          type: 'button',
          disabled: Boolean(problem),
          onclick: () => this.#act({
            a: 'declare', contract: ui.type, trump: ui.trump, helper: ui.helper, discard: [...ui.discards],
          }),
        }, level && !problem ? `Ohlásit: ${LEVEL_NAMES[level]}` : 'Ohlásit závazek'),
        options.can_omyl
          ? h('button.ghost', { type: 'button', onclick: () => { if (window.confirm('Složit karty? Zaplatíš každému flekovanou hru a sedmu.')) this.#act({ a: 'omyl' }); } }, 'Složit karty (omyl)')
          : null,
        problem ? h('span.problem', null, problem) : null),
    );
  }

  #flekActions(options) {
    const deal = this.state.deal;
    const word = options.name;
    const title = word.charAt(0).toUpperCase() + word.slice(1);
    const subsets = options.parts.map((part) => [part]);
    if (options.parts.length === 2) subsets.push([...options.parts]);
    const question = options.stage === 1
      ? `${this.#roleName(deal.declarer)} hlásí ${deal.contract.name}. Věříš mu?`
      : `Soupeř dal ${FLEK_WORDS[options.stage - 2]}. Zvýšíš na ${word}?`;
    append(
        this.actions,
      h('p', null, question),
      h('div.buttons.wrap', null,
        h('button.primary', { type: 'button', onclick: () => this.#act({ a: 'flek', parts: [] }) }, 'Dobrý'),
        subsets.map((parts) => h(
          'button.danger',
          { type: 'button', onclick: () => this.#act({ a: 'flek', parts }) },
          parts.length === 2 ? `${title} na obojí` : `${title} na ${PART_ACC[parts[0]]}`,
        ))),
    );
  }

  #playActions(options) {
    const pending = this.ui.pendingCard;
    if (pending && options.cards.includes(pending) && options.hlasky[pending]) {
      const value = options.hlasky[pending];
      append(
        this.actions,
        h('p', null, `Hraješ ${cardName(pending)} a máš k ní druhou kartu z hlášky.`),
        h('div.buttons', null,
          h('button.primary', { type: 'button', onclick: () => this.#playCard(pending, true) }, `Hlásit ${value}`),
          h('button.ghost', { type: 'button', onclick: () => this.#playCard(pending, false) }, 'Zahrát mlčky'),
          h('button.ghost', { type: 'button', onclick: () => { this.ui.pendingCard = null; this.#render(); } }, 'Vybrat jinou kartu')),
      );
      return;
    }
    const lead = !this.state.deal.trick.length;
    append(
        this.actions,
      h('p.your-turn', null, lead ? 'Vynášíš – klepni na kartu.' : 'Jsi na tahu – klepni na kartu.'),
      Object.keys(options.hlasky).length || !this.autoAnnounce
        ? h('label.check', null,
          h('input', {
            type: 'checkbox',
            checked: this.autoAnnounce,
            onchange: (event) => {
              this.autoAnnounce = event.currentTarget.checked;
              storageSet(AUTO_KEY, this.autoAnnounce ? 'on' : 'off');
            },
          }),
          'Hlášky hlásit automaticky')
        : null,
    );
  }

  #playCard(card, announce) {
    this.ui.pendingCard = null;
    this.#act({ a: 'play', card, announce });
  }

  #onCardClick(card) {
    const deal = this.state.deal;
    const options = deal.options;
    if (!options) return;
    if (options.kind === 'talon') {
      const discards = this.ui.discards;
      if (discards.has(card)) discards.delete(card);
      else if (discards.size < 2) discards.add(card);
      else toast('Do talonu jdou jen dvě karty – nejdřív jednu vrať klepnutím.');
      this.#render();
      return;
    }
    if (options.kind !== 'play') return;
    if (!options.cards.includes(card)) {
      toast(this.#whyNot(card), 'error');
      return;
    }
    if (options.hlasky[card] && !this.autoAnnounce) {
      this.ui.pendingCard = card;
      this.#render();
      return;
    }
    this.#playCard(card, true);
  }

  #whyNot(card) {
    const deal = this.state.deal;
    const contract = deal.contract;
    const hand = deal.hand;
    const isDeclarer = deal.your_role === deal.declarer;
    const announced = contract.type === 'sto' || contract.type === 'betl' || contract.type === 'durch'
      ? [] : [`${contract.trump}7`, contract.helper ? `${contract.helper}7` : null];
    if (isDeclarer && announced.includes(card)) return 'Hlášenou sedmu smíš zahrát až jako poslední kartu její barvy.';
    if (!deal.trick.length) return 'Tuhle kartu teď vynést nelze.';
    const led = deal.trick[0].c[0];
    if (card[0] !== led && hand.some((c) => c[0] === led)) return 'Musíš přiznat barvu.';
    if (card[0] === led) return 'Musíš přebít vyšší kartou.';
    if (contract.trump && card[0] !== contract.trump) return 'Nemáš barvu, musíš hrát trumf.';
    return 'Musíš přebít vyšším trumfem.';
  }

  #renderHand() {
    const state = this.state;
    const deal = state.deal;
    replace(this.hand);
    if (!deal || !deal.hand || state.status === 'waiting' || deal.phase === 'done') return;
    const options = deal.options;
    const plain = Boolean(deal.contract && !deal.contract.trump);
    const cards = sortCards(deal.hand, { plain, trump: deal.contract?.trump ?? null });
    const interactive = options && (options.kind === 'play' || options.kind === 'talon');
    for (const card of cards) {
      const element = cardElement(card, { button: true });
      if (options?.kind === 'play') {
        if (options.cards.includes(card)) element.classList.add('legal');
        else element.classList.add('illegal');
        if (this.ui.pendingCard === card) element.classList.add('selected');
      } else if (options?.kind === 'talon') {
        element.classList.add('legal');
        if (this.ui.discards.has(card)) element.classList.add('selected');
        if (options.talon.includes(card)) element.classList.add('from-talon');
        element.setAttribute('aria-pressed', String(this.ui.discards.has(card)));
      }
      if (interactive) element.addEventListener('click', () => this.#onCardClick(card));
      else element.disabled = true;
      this.hand.append(element);
    }
    this.hand.dataset.count = String(cards.length);
    this.hand.style.setProperty('--n', String(Math.max(cards.length, 2)));
  }

  // ------------------------------------------------------------------ overlay

  #renderOverlay() {
    const state = this.state;
    const deal = state.deal;
    this.centre.classList.toggle('has-overlay', state.status !== 'playing');
    if (state.status === 'playing') {
      this.overlay.hidden = true;
      replace(this.overlay);
      return;
    }
    this.overlay.hidden = false;
    const seated = state.you.seat !== null;
    const me = seated ? state.seats[state.you.seat] : null;
    const free = state.seats.filter((seat) => !seat.occupied).length;
    const children = [];

    if (state.status === 'between' && deal?.result) {
      children.push(this.ui.reveal ? this.#revealPanel() : this.#resultPanel());
    } else {
      children.push(
        h('h2', null, free ? 'Čeká se na hráče' : 'Stůl je plný'),
        h('p', null, free
          ? `Chybí ještě ${plural(free, 'hráč', 'hráči', 'hráčů')}. Pozvi kamarády odkazem, nebo na volné místo posaď počítač.`
          : 'Hra začne, jakmile všichni potvrdí, že jsou připraveni.'),
      );
    }

    const buttons = [];
    if (seated && !free) {
      buttons.push(me.ready
        ? h('span.muted', null, 'Jsi připraven, čeká se na ostatní.')
        : h('button.primary', { type: 'button', onclick: () => this.sendMessage({ type: 'ready' }) },
          state.status === 'between' ? 'Rozdat další hru' : 'Jsem připraven'));
    }
    if (state.status === 'between' && deal?.result) {
      buttons.push(h('button.ghost', { type: 'button', onclick: () => this.#toggle('reveal') },
        this.ui.reveal ? 'Zpět na výsledek' : 'Prohlédnout karty a štychy'));
      if (state.remaining_ms !== null) {
        buttons.push(h('span.muted', null, 'Další hra se rozdá sama za ', h('span.countdown')));
      }
    }
    children.push(h('div.buttons.wrap', null, buttons));
    replace(this.overlay, children);
  }

  #resultPanel() {
    const state = this.state;
    const deal = state.deal;
    const result = deal.result;
    const stake = state.options.stake;
    const declarer = this.#roleName(result.declarer);
    const others = state.seats.filter((s) => s.occupied).length - 1;
    const total = result.units * others;
    const verdict = result.units === 0
      ? 'Vyrovnáno, nikdo neplatí.'
      : result.units > 0
        ? `${declarer} bere ${money(result.units, stake)} od každého, celkem ${money(total, stake)}.`
        : `${declarer} platí každému ${money(-result.units, stake)}, celkem ${money(-total, stake)}.`;

    const rows = result.parts.map((part) => h(
      'tr',
      { class: part.won ? 'won' : 'lost' },
      h('th', null, PART_NAMES[part.part] ?? part.name, part.note ? h('span.part-note', null, part.note) : null),
      h('td', null,
        h('span.outcome', null, part.won ? 'uhráno' : 'neuhráno'),
        part.fleks ? h('span.part-note', null, FLEK_WORDS[part.fleks - 1]) : null),
      h('td.num', null, money(part.units, stake, { sign: true })),
    ));

    const notes = [];
    if (result.outcome === 'approved') notes.push('Sedma bez fleku na sedmu a bez re na hru se nesehrává.');
    if (result.outcome === 'four_helpers') notes.push('Obránce držel čtyři a více pomocných, dvě sedmy se nesehrávají.');
    if (result.outcome === 'missing_seven') notes.push('Aktér neměl obě hlášené sedmy.');
    if (result.declarer_points !== null) {
      notes.push(`Body: ${declarer} ${result.declarer_points}, obrana ${result.defence_points}.`);
    }
    if (result.limited) notes.push(`Platba byla snížena na limit ${money(result.limit, stake)}.`);

    const pb = result.pb_items.map((item) => h(
      'li', null, `${this.#roleName(item.player)}: ${item.label} `, h('b', null, `+${item.points} PB`),
    ));

    return h(
      'div.result',
      null,
      h('h2', null, result.contract ? `${declarer}: ${result.contract.name}` : `${declarer} složil karty`),
      h('p.verdict', { class: result.units > 0 ? 'won' : result.units < 0 ? 'lost' : '' }, verdict),
      h('table.parts', null,
        h('thead', null, h('tr', null,
          h('th', null, 'Část'), h('th', null, 'Výsledek'), h('th.num', null, 'Od každého'))),
        h('tbody', null, rows)),
      notes.length ? h('p.notes', null, notes.join(' ')) : null,
      pb.length ? h('div.pb', null, h('h3', null, 'Prémiové body'), h('ul', null, pb)) : null,
    );
  }

  #revealPanel() {
    const deal = this.state.deal;
    const reveal = deal.reveal;
    const contract = deal.contract;
    const plain = Boolean(contract && !contract.trump);
    const sort = (cards) => sortCards(cards, { plain, trump: contract?.trump ?? null });
    const row = (cards) => h('div.mini-row', null, sort(cards).map((card) => cardElement(card, { small: true })));
    const hands = [0, 1, 2].map((role) => {
      const cards = reveal.play_hands.length ? reveal.play_hands[role] : reveal.remaining[role];
      return h('div.reveal-hand', null, h('h4', null, this.#roleName(role)), row(cards));
    });
    const tricks = reveal.tricks.map((trick, i) => h(
      'li', null,
      h('span.trick-no', null, `${i + 1}.`),
      trick.cards.map(({ p, c }) => h('span', { class: p === trick.winner ? 'took' : '' }, cardElement(c, { small: true }))),
      h('span.muted', null, `bere ${this.#roleName(trick.winner)}`),
    ));
    return h(
      'div.reveal',
      null,
      h('h2', null, 'Karty na začátku sehrávky'),
      hands,
      h('div.reveal-hand', null,
        h('h4', null, 'Talon'),
        h('div.mini-row', null,
          h('span.muted', null, 'ležel: '), reveal.talon.map((card) => cardElement(card, { small: true })),
          reveal.discards.length ? [h('span.muted', null, ' odloženo: '), reveal.discards.map((card) => cardElement(card, { small: true }))] : null)),
      tricks.length ? h('div', null, h('h4', null, 'Štychy'), h('ol.tricks', null, tricks)) : null,
    );
  }

  // --------------------------------------------------------------------- side

  #renderSide() {
    const state = this.state;
    const tab = this.ui.tab;
    this.tabLog.setAttribute('aria-selected', String(tab === 'log'));
    this.tabSheet.setAttribute('aria-selected', String(tab === 'sheet'));
    this.logList.hidden = tab !== 'log';
    this.sheet.hidden = tab !== 'sheet';
    this.side.classList.toggle('open', this.ui.sideOpen);
    if (tab !== 'sheet') return;

    const stake = state.options.stake;
    const seats = state.seats;
    const head = h('tr', null, h('th', null, ''),
      seats.map((seat) => h('th.num', { title: seat.name }, seat.name || '–')));
    const rows = state.history.flatMap((entry) => [
      h('tr.deal-title', null, h('td', { colSpan: seats.length + 1 },
        `${entry.n}. ${entry.contract} – ${entry.declarer_name}: ${money(entry.total, stake, { sign: true })}`)),
      h('tr', null, h('td', null, ''),
        entry.money.map((value, i) => h('td.num', { class: i === entry.declarer ? 'declarer' : '' }, amount(value, stake)))),
    ]);
    const totals = h('tr.totals', null, h('th', null, 'Stav'),
      seats.map((seat) => h('td.num', null, amount(seat.money, stake))));
    const pb = h('tr.totals', null, h('th', null, 'PB'),
      seats.map((seat) => h('td.num', null, String(seat.pb))));
    replace(
      this.sheet,
      state.history.length
        ? h('p.muted', null, 'Částky v korunách, průběžný stav po každé hře.')
        : h('p.muted', null, 'Lístek je zatím prázdný. Po každé hře tu přibude řádek se stavem všech hráčů.'),
      h('div.sheet-scroll', null, h('table', null, h('thead', null, head), h('tbody', null, rows), h('tfoot', null, totals, pb))),
    );
  }

  // --------------------------------------------------------------------- misc

  #confirmLeave() {
    const state = this.state;
    const playing = state.status === 'playing' && state.you.seat !== null;
    if (playing && !window.confirm('Odejít uprostřed hry? Dohraje ji za tebe počítač.')) return;
    this.leaveTable();
  }

  async #invite() {
    const state = this.state;
    const link = `${location.origin}${location.pathname}#t=${state.id}${state.code ? `&c=${state.code}` : ''}`;
    try {
      await navigator.clipboard.writeText(link);
      toast('Odkaz na stůl je ve schránce – pošli ho spoluhráčům.');
    } catch {
      window.prompt('Zkopíruj odkaz na stůl:', link);
    }
  }
}
