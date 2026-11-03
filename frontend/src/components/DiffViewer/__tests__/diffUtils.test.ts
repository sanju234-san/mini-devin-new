import { describe, it, expect } from 'vitest';
import { parseUnifiedDiffText, detectLanguage } from '../diffUtils';
import { TEST_FIXTURE_DIFF_TEXT } from '../../../test-fixtures/testDataFixtures';

describe('Diff Viewer Utilities (Task 6)', () => {
  it('detects programming language accurately from file path extensions', () => {
    expect(detectLanguage('lib/linguist/tokenizer.rb')).toBe('ruby');
    expect(detectLanguage('frontend/src/app/page.tsx')).toBe('typescript');
    expect(detectLanguage('backend/app/main.py')).toBe('python');
    expect(detectLanguage('scripts/deploy.sh')).toBe('shell');
    expect(detectLanguage('unknown_config.xyz')).toBe('plaintext');
  });

  it('parses unified diff text into original and modified code streams', () => {
    const parsed = parseUnifiedDiffText(TEST_FIXTURE_DIFF_TEXT);

    expect(parsed.additions).toBeGreaterThan(0);
    expect(parsed.deletions).toBeGreaterThan(0);
    expect(parsed.originalCode).toContain('if ((unsigned char)*ptr == 0xE2) return 2;');
    expect(parsed.modifiedCode).toContain('if ((unsigned char)*ptr == 0xE2) return 3;');
  });

  it('handles empty or malformed diffs gracefully without crashing', () => {
    const emptyParsed = parseUnifiedDiffText('');
    expect(emptyParsed.additions).toBe(0);
    expect(emptyParsed.deletions).toBe(0);
    expect(emptyParsed.originalCode).toBe('');
    expect(emptyParsed.modifiedCode).toBe('');
  });
});
