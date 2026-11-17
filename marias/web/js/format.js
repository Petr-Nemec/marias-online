// Czech wording and number formatting shared by the views.

export const PART_NAMES = {
  hra: 'hra', sedma: 'sedma', sto: 'sto', betl: 'betl', durch: 'durch',
  dve_sedmy: 'dvě sedmy', ticha_sedma: 'tichá sedma', omyl: 'omyl',
};

// Accusative forms for „flek na …“.
export const PART_ACC = {
  hra: 'hru', sedma: 'sedmu', sto: 'sto', betl: 'betl', durch: 'durch', dve_sedmy: 'dvě sedmy',
};

export const FLEK_WORDS = ['flek', 're', 'tutti', 'boty'];

export const CONTRACT_TYPES = [
  { type: 'sedma', label: 'Sedma', trump: true },
  { type: 'sto', label: 'Sto', trump: true },
  { type: 'sto_sedma', label: 'Sto a sedma', trump: true },
  { type: 'betl', label: 'Betl', trump: false },
  { type: 'durch', label: 'Durch', trump: false },
  { type: 'dve_sedmy', label: 'Dvě sedmy', trump: true, helper: true },
  { type: 'dve_sedmy_sto', label: 'Dvě sedmy a sto', trump: true, helper: true },
];

/** Amount in units of the base stake → „1,20 Kč“. */
export function money(units, stake, { sign = false } = {}) {
  const halere = Math.round(units * stake);
  const abs = Math.abs(halere);
  const text = `${Math.floor(abs / 100)},${String(abs % 100).padStart(2, '0')} Kč`;
  if (halere < 0) return `−${text}`;
  return sign && halere > 0 ? `+${text}` : text;
}

/** Amount without the currency, for dense tables: „+1,20“. */
export function amount(units, stake) {
  return money(units, stake, { sign: true }).replace(' Kč', '');
}

export function plural(count, one, few, many) {
  if (count === 1) return `${count} ${one}`;
  if (count >= 2 && count <= 4) return `${count} ${few}`;
  return `${count} ${many}`;
}

export function clock(ts) {
  const date = new Date(ts);
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}
