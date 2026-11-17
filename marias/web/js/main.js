// Application shell: connection, identity, lobby and switching between views.

import { $, h, replace, storageGet, storageSet, toast } from './dom.js';
import { money, plural } from './format.js';
import { Net } from './net.js';
import { setSoundEnabled, soundEnabled } from './sound.js';
import { TableView } from './table.js';

const TOKEN_KEY = 'marias.token';

const state = {
  player: null,
  info: null,
  lobby: { tables: [], online: 0 },
  table: null,
  pendingName: null,
  invite: readInvite(),
};

const views = {
  login: $('#view-login'),
  lobby: $('#view-lobby'),
  table: $('#view-table'),
};

const net = new Net({
  hello: () => {
    const hello = { type: 'hello' };
    const token = storageGet(TOKEN_KEY);
    if (token) hello.token = token;
    if (state.pendingName) hello.name = state.pendingName;
    return hello;
  },
  message: onMessage,
  status: onStatus,
});

const tableView = new TableView(views.table, {
  send: (message) => {
    if (!net.send(message)) toast('Nejsi připojen – zkouším se spojit znovu.', 'error');
  },
  leave: () => net.send({ type: 'leave_table' }),
});

function readInvite() {
  const params = new URLSearchParams(location.hash.replace(/^#/, ''));
  const table = params.get('t');
  if (!table || !/^[A-Z2-9]{8}$/.test(table)) return null;
  const code = params.get('c');
  return { table, code: code && /^[A-Z2-9]{6}$/.test(code) ? code : null };
}

function show(name) {
  for (const [key, element] of Object.entries(views)) element.hidden = key !== name;
  document.body.dataset.view = name;
}

function onStatus(status) {
  const label = $('#conn');
  const texts = {
    connecting: 'Připojuji…',
    online: '',
    offline: 'Spojení vypadlo, připojuji znovu…',
    stopped: '',
  };
  label.textContent = texts[status] ?? '';
  label.dataset.status = status;
}

function onMessage(message) {
  switch (message.type) {
    case 'welcome':
      state.player = message.player;
      state.info = message.info;
      state.pendingName = null;
      storageSet(TOKEN_KEY, message.token);
      renderName();
      tableView.setPlayer(message.player);
      if (state.invite) {
        const invite = state.invite;
        net.send({ type: 'join_table', table: invite.table, ...(invite.code ? { code: invite.code } : {}) });
      }
      break;
    case 'renamed':
      state.player = message.player;
      renderName();
      tableView.setPlayer(message.player);
      toast('Přezdívka změněna.');
      break;
    case 'lobby':
      state.lobby = message;
      if (!state.table) {
        show('lobby');
        renderLobby();
      }
      break;
    case 'table':
      state.table = message.state;
      state.invite = null;
      history.replaceState(null, '', location.pathname);
      show('table');
      tableView.update(message.state);
      break;
    case 'left':
      state.table = null;
      tableView.reset();
      if (message.reason) toast(message.reason);
      show('lobby');
      renderLobby();
      break;
    case 'error':
      handleError(message);
      break;
    case 'replaced':
      net.stop();
      $('#dlg-replaced').showModal();
      break;
    default:
      break;
  }
}

function handleError(message) {
  if (state.invite) {
    // The invitation could not be used for sitting down – try to watch instead.
    const invite = state.invite;
    state.invite = null;
    if (message.code === 'table_full' || message.code === 'deal_running') {
      net.send({ type: 'watch_table', table: invite.table, ...(invite.code ? { code: invite.code } : {}) });
      return;
    }
    history.replaceState(null, '', location.pathname);
  }
  toast(message.message || 'Něco se nepovedlo.', 'error');
}

// ----------------------------------------------------------------------- lobby

function renderName() {
  const button = $('#btn-name');
  button.hidden = !state.player;
  if (state.player) button.textContent = state.player.name;
}

function seatsText(table) {
  const taken = table.seats.filter((seat) => seat.occupied).length;
  return `${taken}/${table.seats.length}`;
}

function renderLobby() {
  $('#lobby-online').textContent = `Právě online: ${state.lobby.online}`;
  const list = $('#lobby-tables');
  if (!state.lobby.tables.length) {
    replace(
      list,
      h('p.empty', null, 'Žádný otevřený stůl. Založ vlastní – volná místa můžeš obsadit počítačem, než dorazí spoluhráči.'),
    );
    return;
  }
  replace(
    list,
    state.lobby.tables.map((table) => {
      const free = table.seats.some((seat) => !seat.occupied);
      const players = table.seats
        .filter((seat) => seat.occupied)
        .map((seat) => seat.name)
        .join(', ');
      const status = table.status === 'waiting'
        ? 'čeká na hráče'
        : `hraje se ${table.deal_number}. hra`;
      return h(
        'article.table-card',
        null,
        h(
          'div.table-card-main',
          null,
          h('h3', null, table.options.name),
          h('p.muted', null, players || 'zatím nikdo'),
        ),
        h(
          'dl.table-card-facts',
          null,
          h('div', null, h('dt', null, 'Místa'), h('dd', null, seatsText(table))),
          h('div', null, h('dt', null, 'Základ'), h('dd', null, money(1, table.options.stake))),
          h('div', null, h('dt', null, 'Stav'), h('dd', null, status)),
        ),
        h(
          'div.table-card-actions',
          null,
          free && table.status !== 'playing'
            ? h('button.primary', { type: 'button', onclick: () => net.send({ type: 'join_table', table: table.id }) }, 'Přisednout')
            : null,
          h('button.ghost', { type: 'button', onclick: () => net.send({ type: 'watch_table', table: table.id }) }, 'Dívat se'),
          table.spectators ? h('span.muted', null, plural(table.spectators, 'divák', 'diváci', 'diváků')) : null,
        ),
      );
    }),
  );
}

// ---------------------------------------------------------------------- events

$('#login-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const name = $('#login-name').value.trim();
  if (name.length < 2) return;
  state.pendingName = name;
  show('lobby');
  net.start();
});

$('#create-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  net.send({
    type: 'create_table',
    name: form.elements.name.value.trim(),
    seats: Number(form.elements.seats.value),
    stake: Number(form.elements.stake.value),
    turn_seconds: Number(form.elements.turn_seconds.value),
    dealing: form.elements.dealing.value,
    private: form.elements.private.checked,
  });
});

$('#btn-name').addEventListener('click', () => {
  if (state.table) {
    toast('Přezdívku lze změnit jen v herně, mimo stůl.');
    return;
  }
  $('#name-input').value = state.player?.name ?? '';
  $('#dlg-name').showModal();
});

$('#name-form').addEventListener('submit', () => {
  const name = $('#name-input').value.trim();
  if (name.length >= 2) net.send({ type: 'set_name', name });
});

$('#btn-help').addEventListener('click', () => $('#dlg-help').showModal());

for (const button of document.querySelectorAll('[data-close]')) {
  button.addEventListener('click', () => button.closest('dialog').close());
}

$('#btn-takeover').addEventListener('click', () => {
  $('#dlg-replaced').close();
  net.start();
});

function renderSound() {
  const button = $('#btn-sound');
  const on = soundEnabled();
  button.textContent = on ? 'Zvuk zapnutý' : 'Zvuk vypnutý';
  button.setAttribute('aria-pressed', String(on));
}

$('#btn-sound').addEventListener('click', () => {
  setSoundEnabled(!soundEnabled());
  renderSound();
});

renderSound();

if (storageGet(TOKEN_KEY)) {
  show('lobby');
  net.start();
} else {
  show('login');
  $('#login-name').focus();
}
