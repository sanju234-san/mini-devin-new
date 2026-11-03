/**
 * Regression test for Chainlit Console clipboard paste fix.
 *
 * Verifies:
 * 1. Without paste_fix.js: Chainlit 2.0.5 onPaste cancels paste events on text and drops content.
 * 2. With paste_fix.js:
 *    - Plain text pasting (Ctrl+V, right-click paste) works and updates element content.
 *    - Multiline text pasting preserves newlines.
 *    - GitHub issue URLs paste accurately without mangling.
 *    - File/image paste events without text/plain are passed through to file upload handler.
 *    - Input events are dispatched for React state synchronization.
 *    - Normal typing and Enter key events are preserved without interference.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

// Minimal DOM simulation for event capture/bubble phases and contenteditable
class MockEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.bubbles = !!init.bubbles;
    this.cancelable = !!init.cancelable;
    this.defaultPrevented = false;
    this._immediatePropagationStopped = false;
    this.target = null;
    this.clipboardData = init.clipboardData || null;
  }

  preventDefault() {
    this.defaultPrevented = true;
  }

  stopImmediatePropagation() {
    this._immediatePropagationStopped = true;
  }
}

class MockElement {
  constructor(id, tagName = 'div') {
    this.id = id;
    this.tagName = tagName.toUpperCase();
    this.nodeType = 1;
    this.contentEditable = 'true';
    this.textContent = '';
    this.parentElement = null;
    this.children = [];
    this._listeners = [];
  }

  closest(selector) {
    if (selector === '#' + this.id) return this;
    if (this.parentElement) return this.parentElement.closest(selector);
    return null;
  }

  contains(node) {
    if (node === this) return true;
    for (const child of this.children) {
      if (child.contains(node)) return true;
    }
    return false;
  }

  focus() {}

  appendChild(child) {
    this.children.push(child);
    child.parentElement = this;
    this.textContent += child.textContent;
  }

  addEventListener(type, listener, useCapture = false) {
    this._listeners.push({ type, listener, useCapture: !!useCapture });
  }

  removeEventListener(type, listener) {
    this._listeners = this._listeners.filter(l => !(l.type === type && l.listener === listener));
  }

  dispatchEvent(event) {
    event.target = this;
    // Dispatch in DOM tree order: window capture -> target
    const windowListeners = global.window._listeners.filter(l => l.type === event.type);
    const targetListeners = this._listeners.filter(l => l.type === event.type);

    // 1. Capture phase on window
    for (const l of windowListeners) {
      if (l.useCapture) {
        l.listener(event);
        if (event._immediatePropagationStopped) return !event.defaultPrevented;
      }
    }

    // 2. Target phase
    for (const l of targetListeners) {
      l.listener(event);
      if (event._immediatePropagationStopped) return !event.defaultPrevented;
    }

    // 3. Bubble phase on window
    for (const l of windowListeners) {
      if (!l.useCapture) {
        l.listener(event);
        if (event._immediatePropagationStopped) return !event.defaultPrevented;
      }
    }

    return !event.defaultPrevented;
  }
}

// Setup global mock browser environment
global.Node = { TEXT_NODE: 3, ELEMENT_NODE: 1 };
global.window = {
  _listeners: [],
  addEventListener(type, listener, useCapture = false) {
    this._listeners.push({ type, listener, useCapture: !!useCapture });
  },
  removeEventListener(type, listener) {
    this._listeners = this._listeners.filter(l => !(l.type === type && l.listener === listener));
  },
  getSelection() {
    return {
      rangeCount: 0,
      getRangeAt() { return null; },
      removeAllRanges() {},
      addRange() {}
    };
  }
};
global.document = {
  activeElement: null,
  createTextNode(text) {
    return { nodeType: 3, textContent: text, contains() { return false; } };
  },
  createRange() {
    return {
      selectNodeContents() {},
      collapse() {},
      deleteContents() {},
      insertNode(node) { global.document.activeElement.appendChild(node); },
      setStartAfter() {}
    };
  },
  execCommand(cmd, showUI, value) {
    if (cmd === 'insertText') {
      if (global.document.activeElement) {
        global.document.activeElement.textContent += value;
        return true;
      }
    }
    return false;
  }
};
global.Event = MockEvent;

console.log('--- TEST 1: Chainlit 2.0.5 native buggy behavior ---');
const chatInputBuggy = new MockElement('chat-input');
global.document.activeElement = chatInputBuggy;

// Chainlit 2.0.5 native buggy onPaste handler:
let fileUploadTriggeredBuggy = false;
const buggyChainlitPasteHandler = (L) => {
  L.preventDefault(); // <-- The unconditional preventDefault() bug
  if (L.clipboardData && L.clipboardData.items) {
    if (L.clipboardData.getData('text/plain')) return;
    fileUploadTriggeredBuggy = true;
  }
};
chatInputBuggy.addEventListener('paste', buggyChainlitPasteHandler, false);

const textPasteEvent1 = new MockEvent('paste', {
  bubbles: true,
  cancelable: true,
  clipboardData: {
    getData: (format) => (format === 'text/plain' ? 'https://github.com/psf/requests/issues/100' : ''),
    items: [{ kind: 'string', type: 'text/plain' }]
  }
});
chatInputBuggy.dispatchEvent(textPasteEvent1);

assert.strictEqual(textPasteEvent1.defaultPrevented, true, 'Default was prevented by buggy handler');
assert.strictEqual(chatInputBuggy.textContent, '', 'Buggy behavior left textContent empty');
console.log(' Confirmed: Chainlit native handler prevents paste and drops text.');

console.log('\n--- TEST 2: Loading paste_fix.js and verifying text paste ---');
// Reset listeners on window
global.window._listeners = [];

// Load paste_fix.js script content
const scriptPath = path.resolve(__dirname, '../chainlit_console/public/paste_fix.js');
assert.ok(fs.existsSync(scriptPath), 'paste_fix.js exists in chainlit_console/public');
const scriptCode = fs.readFileSync(scriptPath, 'utf-8');
eval(scriptCode);

const chatInputFixed = new MockElement('chat-input');
global.document.activeElement = chatInputFixed;
chatInputFixed.addEventListener('paste', buggyChainlitPasteHandler, false);

let inputEventCount = 0;
chatInputFixed.addEventListener('input', () => {
  inputEventCount++;
});

// Paste single line / URL
const textPasteEvent2 = new MockEvent('paste', {
  bubbles: true,
  cancelable: true,
  clipboardData: {
    getData: (format) => (format === 'text/plain' ? 'https://github.com/psf/requests/issues/100' : ''),
    items: [{ kind: 'string', type: 'text/plain' }]
  }
});
chatInputFixed.dispatchEvent(textPasteEvent2);

assert.strictEqual(
  chatInputFixed.textContent,
  'https://github.com/psf/requests/issues/100',
  'Text was inserted into #chat-input'
);
assert.strictEqual(inputEventCount, 1, 'Input event was dispatched for React state synchronization');
console.log(' Text paste works: URL inserted and input event fired.');

console.log('\n--- TEST 3: Multiline pasted text ---');
const multilineText = 'First line of instructions\nSecond line of code\nThird line';
const multilinePasteEvent = new MockEvent('paste', {
  bubbles: true,
  cancelable: true,
  clipboardData: {
    getData: (format) => (format === 'text/plain' ? multilineText : ''),
    items: [{ kind: 'string', type: 'text/plain' }]
  }
});
chatInputFixed.textContent = '';
chatInputFixed.dispatchEvent(multilinePasteEvent);

assert.strictEqual(chatInputFixed.textContent, multilineText, 'Multiline text preserved correctly');
assert.strictEqual(inputEventCount, 2, 'Input event fired on multiline paste');
console.log(' Multiline paste works: all lines preserved.');

console.log('\n--- TEST 4: File/screenshot paste passthrough ---');
let fileUploadTriggeredFixed = false;
chatInputFixed.removeEventListener('paste', buggyChainlitPasteHandler);
chatInputFixed.addEventListener('paste', (L) => {
  L.preventDefault();
  if (L.clipboardData && L.clipboardData.items) {
    if (L.clipboardData.getData('text/plain')) return;
    fileUploadTriggeredFixed = true;
  }
});

const filePasteEvent = new MockEvent('paste', {
  bubbles: true,
  cancelable: true,
  clipboardData: {
    getData: () => '', // No plain text
    items: [{ kind: 'file', type: 'image/png' }]
  }
});
chatInputFixed.dispatchEvent(filePasteEvent);

assert.strictEqual(fileUploadTriggeredFixed, true, 'File paste correctly reached Chainlit handler');
console.log(' File/screenshot paste is preserved for spontaneous file uploads.');

console.log('\n--- TEST 5: Normal typing and Enter key untouched ---');
let enterKeyHandled = false;
chatInputFixed.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    enterKeyHandled = true;
  }
});
const enterEvent = new MockEvent('keydown', { bubbles: true, cancelable: true });
enterEvent.key = 'Enter';
chatInputFixed.dispatchEvent(enterEvent);
assert.strictEqual(enterKeyHandled, true, 'Enter key is completely unaffected');
console.log(' Normal typing & Enter keys operate with zero interference.');

console.log('\nALL 5 REGRESSION TESTS PASSED SUCCESSFULLY!');
