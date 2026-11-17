// Tiny synthesised cues (no audio files): your turn, card played, deal finished.

import { storageGet, storageSet } from './dom.js';

const KEY = 'marias.sound';
let enabled = storageGet(KEY) !== 'off';
let context = null;

export const soundEnabled = () => enabled;

export function setSoundEnabled(value) {
  enabled = value;
  storageSet(KEY, value ? 'on' : 'off');
}

function tone(frequency, start, duration, gain) {
  const oscillator = context.createOscillator();
  const envelope = context.createGain();
  oscillator.type = 'triangle';
  oscillator.frequency.value = frequency;
  envelope.gain.setValueAtTime(0, context.currentTime + start);
  envelope.gain.linearRampToValueAtTime(gain, context.currentTime + start + 0.01);
  envelope.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + start + duration);
  oscillator.connect(envelope).connect(context.destination);
  oscillator.start(context.currentTime + start);
  oscillator.stop(context.currentTime + start + duration + 0.02);
}

export function play(kind) {
  if (!enabled) return;
  try {
    context ??= new (window.AudioContext || window.webkitAudioContext)();
    if (context.state === 'suspended') context.resume();
    if (kind === 'turn') {
      tone(660, 0, 0.12, 0.08);
      tone(880, 0.1, 0.16, 0.08);
    } else if (kind === 'card') {
      tone(220, 0, 0.05, 0.05);
    } else if (kind === 'done') {
      tone(523, 0, 0.12, 0.07);
      tone(659, 0.11, 0.12, 0.07);
      tone(784, 0.22, 0.2, 0.07);
    }
  } catch {
    /* audio is a nicety; never let it break the game */
  }
}
