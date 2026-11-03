import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';
import React from 'react';

// Polyfill window.matchMedia for JSDOM
if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

// Mock @monaco-editor/react DiffEditor
vi.mock('@monaco-editor/react', () => ({
  DiffEditor: ({ original, modified }: { original: string; modified: string }) =>
    React.createElement('div', { 'data-testid': 'mock-monaco-diff-editor' }, [
      React.createElement('pre', { key: 'orig', 'data-testid': 'mock-diff-original' }, original),
      React.createElement('pre', { key: 'mod', 'data-testid': 'mock-diff-modified' }, modified),
    ]),
  Editor: () => React.createElement('div', { 'data-testid': 'mock-monaco-editor' }),
}));

// Mock xterm
vi.mock('xterm', () => ({
  Terminal: class {
    open = vi.fn();
    write = vi.fn();
    clear = vi.fn();
    dispose = vi.fn();
    onData = vi.fn();
  },
}));
