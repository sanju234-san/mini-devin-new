import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { getWebSocketUri, useAgentRunSocket } from '../useAgentRunSocket';
import { TEST_FIXTURE_EVENT_ENVELOPE } from '../../test-fixtures/testDataFixtures';

// Mock WebSocket implementation for headless JSDOM testing
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSING = 2;
  readonly CLOSED = 3;

  url: string;
  readyState: number = 0;
  onopen: ((ev?: any) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev: any) => void) | null = null;
  onclose: ((ev: any) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    setTimeout(() => {
      this.readyState = 1; // OPEN
      this.onopen?.();
    }, 10);
  }

  send(data: string) {
    // no-op
  }

  close(code = 1000, reason = 'Normal closure') {
    this.readyState = 3; // CLOSED
    this.onclose?.({ code, reason });
  }
}

describe('WebSocket Client & Hook (Task 3)', () => {
  const originalWebSocket = global.WebSocket;

  beforeEach(() => {
    global.WebSocket = MockWebSocket as any;
  });

  afterEach(() => {
    global.WebSocket = originalWebSocket;
  });

  it('correctly derives ws:// URI from configured HTTP API base', () => {
    const uriWithRun = getWebSocketUri('run-8924a');
    expect(uriWithRun).toMatch(/^ws:\/\/|wss:\/\//);
    expect(uriWithRun).toContain('/ws/runs/run-8924a');

    const uriWithoutRun = getWebSocketUri();
    expect(uriWithoutRun).toMatch(/^ws:\/\/|wss:\/\//);
    expect(uriWithoutRun).toContain('/ws/runs');
  });

  it('manages connection lifecycle: CONNECTING -> CONNECTED', async () => {
    const { result } = renderHook(() =>
      useAgentRunSocket('run-8924a', { autoConnect: true })
    );

    expect(result.current.connectionState).toBe('CONNECTING');

    // Wait for mock WebSocket onopen
    await act(async () => {
      await new Promise((r) => setTimeout(r, 25));
    });

    expect(result.current.connectionState).toBe('CONNECTED');
    expect(result.current.readyState).toBe(1);
  });

  it('ingests and buffers incoming agent event envelopes conforming to contract', async () => {
    let activeSocketInstance: MockWebSocket | null = null;
    const OriginalMock = global.WebSocket;
    global.WebSocket = class extends MockWebSocket {
      constructor(url: string) {
        super(url);
        activeSocketInstance = this;
      }
    } as any;

    const { result } = renderHook(() =>
      useAgentRunSocket('run-8924a', { autoConnect: true })
    );

    await act(async () => {
      await new Promise((r) => setTimeout(r, 20));
    });

    // Simulate incoming message event
    act(() => {
      activeSocketInstance?.onmessage?.({
        data: JSON.stringify(TEST_FIXTURE_EVENT_ENVELOPE),
      });
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.latestEvent?.agent).toBe('Coder');
    expect(result.current.latestEvent?.tool).toBe('patch_file');
    expect(result.current.telemetry.ingestedEventCount).toBe(1);

    global.WebSocket = OriginalMock;
  });

  it('cleans up connection when unmounted', async () => {
    const closeSpy = vi.spyOn(MockWebSocket.prototype, 'close');

    const { unmount } = renderHook(() =>
      useAgentRunSocket('run-8924a', { autoConnect: true })
    );

    await act(async () => {
      await new Promise((r) => setTimeout(r, 25));
    });

    unmount();
    expect(closeSpy).toHaveBeenCalled();
  });
});
