/**
 * Type definitions for Task 6 — Code & Diff Viewing (DiffViewer).
 *
 * Modeled directly on the Diff and FileChange schemas from docs/design/schemas.md
 * and backend/app/agents/schemas.py.
 */

export type ChangeType = 'add' | 'modify' | 'delete';

export interface FileDiffItem {
  /** Relative file path */
  path: string;
  /** Type of change */
  changeType: ChangeType;
  /** Language identifier for Monaco Editor (e.g. 'ruby', 'typescript', 'python', 'json') */
  language?: string;
  /** Unified diff text if available */
  diffText?: string;
  /** Original file content (before changes) */
  originalCode: string;
  /** Modified file content (after changes) */
  modifiedCode: string;
  /** Number of added lines */
  additions: number;
  /** Number of deleted lines */
  deletions: number;
  /** Associated requirement IDs from plan (e.g. ['R1', 'R2']) */
  requirementIds?: string[];
}

export interface DiffMetadata {
  runId: string;
  repository?: string;
  issueId?: string;
  issueTitle?: string;
  branch?: string;
  planVersionId?: string;
  changeSummary?: string;
  testsAdded?: string[];
}

export interface DiffViewerData {
  metadata: DiffMetadata;
  files: FileDiffItem[];
  totalAdditions: number;
  totalDeletions: number;
}

export type DiffRenderMode = 'inline' | 'side-by-side';

export type DiffViewerState = 'real' | 'preview-active' | 'preview-loading' | 'preview-empty';
