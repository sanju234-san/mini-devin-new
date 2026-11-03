import React from 'react';
import type { DiffViewerData, FileDiffItem } from './types';

export const CopyIcon: React.FC<{ className?: string }> = ({ className = 'w-3.5 h-3.5' }) =>
  React.createElement(
    'svg',
    {
      className,
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: '2',
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
    },
    React.createElement('rect', { x: '9', y: '9', width: '13', height: '13', rx: '2', ry: '2' }),
    React.createElement('path', { d: 'M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1' })
  );

export const CheckIcon: React.FC<{ className?: string }> = ({ className = 'w-3.5 h-3.5' }) =>
  React.createElement(
    'svg',
    {
      className,
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: '2',
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
    },
    React.createElement('polyline', { points: '20 6 9 17 4 12' })
  );


/**
 * Maps file extension to a Monaco language identifier.
 */
export function detectLanguage(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'rb':
      return 'ruby';
    case 'ts':
    case 'tsx':
      return 'typescript';
    case 'js':
    case 'jsx':
    case 'mjs':
    case 'cjs':
      return 'javascript';
    case 'py':
      return 'python';
    case 'json':
      return 'json';
    case 'css':
      return 'css';
    case 'html':
      return 'html';
    case 'md':
      return 'markdown';
    case 'yaml':
    case 'yml':
      return 'yaml';
    case 'sh':
    case 'bash':
      return 'shell';
    case 'go':
      return 'go';
    case 'rs':
      return 'rust';
    case 'sql':
      return 'sql';
    default:
      return 'plaintext';
  }
}

/**
 * Reconstructs original and modified code streams from unified diff text.
 */
export function parseUnifiedDiffText(diffText: string): {
  originalCode: string;
  modifiedCode: string;
  additions: number;
  deletions: number;
} {
  const lines = diffText.split('\n');
  const origLines: string[] = [];
  const modLines: string[] = [];
  let additions = 0;
  let deletions = 0;
  let inHunk = false;

  for (const line of lines) {
    if (line.startsWith('@@')) {
      inHunk = true;
      continue;
    }
    if (!inHunk) continue;

    if (line.startsWith('+')) {
      additions++;
      modLines.push(line.slice(1));
    } else if (line.startsWith('-')) {
      deletions++;
      origLines.push(line.slice(1));
    } else if (line.startsWith(' ')) {
      origLines.push(line.slice(1));
      modLines.push(line.slice(1));
    } else if (line === '') {
      origLines.push('');
      modLines.push('');
    }
  }

  // If no @@ hunk headers were detected but text is present, treat as added code
  if (!inHunk && diffText.trim().length > 0) {
    return {
      originalCode: '',
      modifiedCode: diffText,
      additions: lines.length,
      deletions: 0,
    };
  }

  return {
    originalCode: origLines.join('\n'),
    modifiedCode: modLines.join('\n'),
    additions,
    deletions,
  };
}

/**
 * Synthetic development preview dataset matching the Stitch visual design reference.
 * Strictly used for developer preview/simulator mode, kept isolated from real API calls.
 */
export const SYNTHETIC_PREVIEW_DIFF: DiffViewerData = {
  metadata: {
    runId: 'run-8924a',
    repository: 'octocat/linguist',
    issueId: '482',
    issueTitle: 'UTF-8 encoding error in tokenizer',
    branch: 'fix/utf8-tokenizer-boundaries',
    planVersionId: 'v1',
    changeSummary: 'Enforce multibyte UTF-8 boundary handling in tokenizer and append regression tests.',
  },
  files: [
    {
      path: 'lib/linguist/tokenizer.rb',
      changeType: 'modify',
      language: 'ruby',
      additions: 28,
      deletions: 12,
      requirementIds: ['R1', 'R2'],
      originalCode: `module Linguist
  class Tokenizer
    def tokenize(source)
      return [] if source.nil? || source.empty?

      tokens = source.scan(/\\w+|\\S/)
      tokens.map(&:downcase)
    end
  end
end
`,
      modifiedCode: `module Linguist
  class Tokenizer
    def tokenize(source)
      return [] if source.nil? || source.strip.empty?

      # Handle multibyte UTF-8 boundaries safely
      encoded = source.force_encoding('UTF-8')
      tokens = encoded.valid_encoding? ? encoded.scan(/\\w+|\\S/) : []
      tokens.map(&:strip).reject(&:empty?)
    end
  end
end
`,
    },
    {
      path: 'test/test_tokenizer.rb',
      changeType: 'modify',
      language: 'ruby',
      additions: 14,
      deletions: 6,
      requirementIds: ['R3'],
      originalCode: `require 'minitest/autorun'
require_relative '../lib/linguist/tokenizer'

class TestTokenizer < Minitest::Test
  def setup
    @tokenizer = Linguist::Tokenizer.new
  end

  def test_basic_tokenization
    tokens = @tokenizer.tokenize("hello world")
    assert_equal ["hello", "world"], tokens
  end
end
`,
      modifiedCode: `require 'minitest/autorun'
require_relative '../lib/linguist/tokenizer'

class TestTokenizer < Minitest::Test
  def setup
    @tokenizer = Linguist::Tokenizer.new
  end

  def test_basic_tokenization
    tokens = @tokenizer.tokenize("hello world")
    assert_equal ["hello", "world"], tokens
  end

  def test_multibyte_utf8_boundaries
    # Regression test for Issue #482
    multibyte_str = "int main() { char *s = \\"こんにちは\\"; return 0; }"
    tokens = @tokenizer.tokenize(multibyte_str)
    assert tokens.include?("こんにちは")
  end
end
`,
    },
    {
      path: 'Gemfile.lock',
      changeType: 'modify',
      language: 'plaintext',
      additions: 0,
      deletions: 0,
      requirementIds: ['R2'],
      originalCode: `GEM
  remote: https://rubygems.org/
  specs:
    minitest (5.20.0)
    rake (13.1.0)

DEPENDENCIES
  minitest (~> 5.20)
  rake (~> 13.0)

RUBY VERSION
   ruby 3.2.2p53
`,
      modifiedCode: `GEM
  remote: https://rubygems.org/
  specs:
    minitest (5.20.0)
    rake (13.1.0)

DEPENDENCIES
  minitest (~> 5.20)
  rake (~> 13.0)

RUBY VERSION
   ruby 3.2.2p53
`,
    },
  ],
  totalAdditions: 42,
  totalDeletions: 18,
};
