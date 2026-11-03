/**
 * Mini-Devin Chainlit Console - Clipboard Paste Fix
 *
 * Root Cause:
 * In Chainlit 2.0.5, the message input container component registers an onPaste
 * handler on #chat-input. In that handler, `event.preventDefault()` is executed
 * unconditionally at the start. When plain text is pasted, the handler returns early
 * without inserting the text, leaving default browser paste canceled and the input empty.
 *
 * Solution:
 * Intercept the paste event in the capturing phase on window before it reaches
 * Chainlit's bubble/target handler.
 * - If text/plain is in the clipboard:
 *   1. Stop immediate propagation to prevent Chainlit's faulty onPaste from executing.
 *   2. Prevent default browser paste.
 *   3. Insert the plain text into #chat-input at current selection/cursor.
 *   4. Dispatch an 'input' event so Chainlit's React onInput handler updates message state.
 * - If no text is present (e.g. file/screenshot paste), allow event to propagate to
 *   Chainlit's native file upload handler.
 */

(function () {
  'use strict';

  function getChatInput(target) {
    if (!target) return null;
    if (target.nodeType === Node.TEXT_NODE) {
      target = target.parentElement;
    }
    if (!target || typeof target.closest !== 'function') return null;
    return target.closest('#chat-input');
  }

  function insertTextAtSelection(element, text) {
    element.focus();

    let success = false;
    try {
      // document.execCommand handles contenteditable selection,
      // replaces highlighted text, moves cursor, and preserves undo stack.
      success = document.execCommand('insertText', false, text);
    } catch (e) {
      success = false;
    }

    if (!success) {
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0) {
        let range = sel.getRangeAt(0);
        // Ensure range is inside chatInput
        if (!element.contains(range.commonAncestorContainer)) {
          range = document.createRange();
          range.selectNodeContents(element);
          range.collapse(false);
          sel.removeAllRanges();
          sel.addRange(range);
        }
        range.deleteContents();
        const textNode = document.createTextNode(text);
        range.insertNode(textNode);
        range.setStartAfter(textNode);
        range.collapse(true);
        sel.removeAllRanges();
        sel.addRange(range);
      } else {
        element.appendChild(document.createTextNode(text));
      }
    }

    // Dispatch input event so Chainlit's React onInput handler updates state
    const inputEvent = new Event('input', { bubbles: true, cancelable: true });
    element.dispatchEvent(inputEvent);
  }

  function onPasteCapture(e) {
    const chatInput = getChatInput(e.target) || getChatInput(document.activeElement);
    if (!chatInput) {
      return;
    }

    const clipboardData = e.clipboardData || window.clipboardData;
    if (!clipboardData) {
      return;
    }

    const text = clipboardData.getData('text/plain');
    if (!text) {
      // No plain text present (e.g. pasted file or screenshot).
      // Allow event to proceed to Chainlit's file upload handler.
      return;
    }

    // Stop Chainlit's native handler from calling e.preventDefault() and dropping text
    e.stopImmediatePropagation();
    e.preventDefault();

    insertTextAtSelection(chatInput, text);
  }

  // Attach in capturing phase to intercept before target/bubbling listeners
  window.addEventListener('paste', onPasteCapture, true);
})();
