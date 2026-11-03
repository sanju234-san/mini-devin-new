"""
Query Transformation and Analysis for Mini-Devin Retrieval.

Extracts technical code identifiers, keywords, and domain concepts from issue
titles and descriptions. Optionally attempts LLM-based query rewriting when the
shared LLM provider client is functional, but gracefully falls back to deterministic
analysis when the LLM provider is not available.

Also provides issue text cleaning for retrieval and triage.
This is not a security control; the injection scan runs on the raw text before Triage;
cleaned text remains untrusted. Cleaning removes noise only.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, NamedTuple, Optional

logger = logging.getLogger(__name__)


# ── Text Cleaning (HEAD) ─────────────────────────────────────────────

# Allowlist of tag names for bounded HTML tag removal
_ALLOWED_TAGS = (
    r"a|b|blockquote|br|code|details|div|em|h1|h2|h3|h4|h5|h6|hr|i|img|kbd|"
    r"li|ol|p|picture|pre|source|span|strong|sub|summary|sup|table|tbody|td|th|thead|tr|ul"
)
_TAG_RE = re.compile(rf"</?(?:{_ALLOWED_TAGS})(?=[\s/>])[^<>]{{0,200}}>", re.IGNORECASE)

# Bounded markdown image removal pattern
_IMAGE_RE = re.compile(r"!\[[^\[\]]{0,300}\]\([^()\s]{0,500}\)")

# Checkbox markers at the start of a line only; does not consume newline
_CHECKBOX_RE = re.compile(r"^[ \t]*[-*][ \t]*\[[ xX]\][ \t]*", re.MULTILINE)

# GitHub issue-template: ### heading lines (e.g. "### Initial Checks", "### Description")
_TEMPLATE_HEADING_RE = re.compile(r"^[ \t]*###[^\n]*", re.MULTILINE)

# Section names whose checked checklist items are boilerplate
_BOILERPLATE_SECTIONS = re.compile(
    r"(?:Initial\s+Checks?|Discussed\s+in|Affected\s+Components?|Before\s+you\s+begin)",
    re.IGNORECASE,
)

# A checked checklist line (text captured)
_CHECKED_LINE_RE = re.compile(r"^[ \t]*[-*][ \t]*\[[xX]\][ \t]*(.*)$")

# Checked items starting with these phrases are template boilerplate anywhere
_BOILERPLATE_PHRASE_RE = re.compile(
    r"^(?:I\s+confirm|I\s+(?:have\s+)?searched|I\s+added\s+a\s+descriptive\s+title)",
    re.IGNORECASE,
)


def _strip_template_blocks(text: str) -> str:
    """Drop ### template headings and boilerplate checked checklist items.

    Checked items are removed only inside boilerplate sections or when they start
    with a known template phrase. All other checklist text is kept (marker only
    is stripped later by _CHECKBOX_RE).
    """
    result: list[str] = []
    in_boilerplate = False
    for line in text.split("\n"):
        if _TEMPLATE_HEADING_RE.match(line):
            in_boilerplate = bool(_BOILERPLATE_SECTIONS.search(line))
            result.append("")
            continue
        m = _CHECKED_LINE_RE.match(line)
        if m and (in_boilerplate or _BOILERPLATE_PHRASE_RE.match(m.group(1))):
            result.append("")
            continue
        result.append(line)
    return "\n".join(result)

# Inline code: single-backtick spans on one line of at most 300 characters
_INLINE_RE = re.compile(r"`[^`\n]{0,300}`")

# Control characters except \n and \t (all Cc codepoints in Unicode are <= 0x9f)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

_GREETING_WORDS = {"hi", "hello", "hey", "dear"}
_GREETING_AUDIENCE = {
    "all", "everyone", "team", "there", "folks", "guys",
    "maintainers", "developers", "sir", "madam",
}

_SIGNOFF_EXACT = {
    ("thanks",),
    ("thank", "you"),
    ("many", "thanks"),
    ("thanks", "in", "advance"),
    ("thanks", "a", "lot"),
    ("regards",),
    ("best", "regards"),
    ("kind", "regards"),
    ("cheers",),
    ("best",),
}


def _is_pure_greeting(line: str) -> bool:
    """Return True if line is purely a greeting."""
    stripped = line.strip().rstrip(".,!?:; \t").lower()
    words = stripped.split()
    if not words:
        return False
    if len(words) == 1 and words[0] in _GREETING_WORDS:
        return True
    if len(words) == 2 and words[0] in _GREETING_WORDS and words[1] in _GREETING_AUDIENCE:
        return True
    return False


def _is_pure_signoff(line: str) -> bool:
    """Return True if line is purely a sign-off."""
    stripped = line.strip().rstrip(".,!?:; \t").lower()
    words = tuple(stripped.split())
    return words in _SIGNOFF_EXACT


def clean_issue_text(text: str | None, max_chars: int = 4000) -> str:
    """Clean noisy markdown issue text for retrieval and triage.
    This is not a security control; cleaned text remains untrusted.
    """
    if max_chars <= 0:
        return ""
    if text is None or not text.strip():
        return ""

    # 2. Normalise NFKC, convert line endings, remove control characters except \n and \t
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHAR_RE.sub("", text)
    if not text.strip():
        return ""

    # 3. Split on triple-backtick fences; inside fences kept as is (except trailing whitespace)
    parts = text.split("```")
    fences: dict[str, str] = {}
    inlines: dict[str, str] = {}
    assembled_parts: list[str] = []
    inline_counter = 0

    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Inside code fence
            cleaned_code = "\n".join(line.rstrip(" \t") for line in part.split("\n"))
            token = f"\x00FENCE_{i}\x00"
            if i == len(parts) - 1 and len(parts) % 2 == 0:
                fences[token] = f"```{cleaned_code}"
            else:
                fences[token] = f"```{cleaned_code}```"
            assembled_parts.append(token)
        else:
            # Outside code fence: protect single-backtick inline code first
            def _protect_inline(m: re.Match) -> str:
                nonlocal inline_counter
                t = f"\x00INLINE_{inline_counter}\x00"
                inlines[t] = m.group(0)
                inline_counter += 1
                return t

            out = _INLINE_RE.sub(_protect_inline, part)

            # 4. Remove HTML comments (unclosed removed to end of segment)
            out = re.sub(r"<!--[\s\S]*?(?:-->|$)", "", out)
            # Remove allowlisted HTML tags with bounded length, keeping inner text
            out = _TAG_RE.sub("", out)
            # Remove bounded markdown images
            out = _IMAGE_RE.sub("", out)
            # Remove bare http/https URLs
            out = re.sub(r"https?://\S+", "", out)
            # Strip issue-template headings and boilerplate checklist items
            out = _strip_template_blocks(out)
            # Strip remaining checkbox markers only at start of line
            out = _CHECKBOX_RE.sub("", out)
            # Remove category So (symbols/emoji) and Cf (invisible chars, directional overrides)
            if not out.isascii():
                out = "".join(c for c in out if c.isascii() or unicodedata.category(c) not in ("So", "Cf"))
            assembled_parts.append(out)

    combined = "".join(assembled_parts)

    # 7. Greeting and sign-off removal
    lines = combined.split("\n")
    non_empty_indices = [idx for idx, line in enumerate(lines) if line.strip()]
    first_3 = set(non_empty_indices[:3])
    last_3 = set(non_empty_indices[-3:])

    filtered_lines: list[str] = []
    for idx, line in enumerate(lines):
        if "\x00FENCE_" in line or "\x00INLINE_" in line:
            filtered_lines.append(line)
            continue

        if idx in first_3 and _is_pure_greeting(line):
            continue
        if idx in last_3 and _is_pure_signoff(line):
            continue

        filtered_lines.append(line)

    # 8. Collapse runs of spaces/tabs, strip trailing whitespace, collapse newlines
    combined = "\n".join(filtered_lines)
    combined = re.sub(r"[ \t]+", " ", combined)
    combined = "\n".join(line.rstrip(" \t") for line in combined.split("\n"))
    combined = re.sub(r"\n{3,}", "\n\n", combined)
    combined = combined.strip("\n")

    # Restore inline code spans
    if inlines:
        combined = re.sub(r"\x00INLINE_\d+\x00", lambda m: inlines[m.group(0)], combined)

    # Restore fenced code blocks
    if fences:
        combined = re.sub(r"\x00FENCE_\d+\x00", lambda m: fences[m.group(0)], combined)

    combined = combined.strip("\n")
    if not combined:
        return ""

    # 9. Truncation to max_chars
    if len(combined) > max_chars:
        suffix = "\n[truncated]"
        if max_chars <= len(suffix):
            combined = suffix[:max_chars]
        else:
            budget = max_chars - len(suffix)
            cut_pos = combined.rfind("\n", 0, budget + 1)
            if cut_pos != -1:
                combined = combined[:cut_pos] + suffix
            else:
                combined = combined[:budget] + suffix

    return combined


# ── Query Analysis (df19790) ─────────────────────────────────────────

# Common English stopwords to ignore in code retrieval keywords
_STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with",
    "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves", "issue", "bug", "fix", "please",
    "error", "fail", "failed", "failing", "fails", "problem", "broken",
})

# Regex patterns for code-specific identifiers
_CAMEL_CASE_RE = re.compile(r"\b[A-Z][a-zA-Z0-9]+(?:[A-Z][a-zA-Z0-9]*)+\b")
_SNAKE_CASE_RE = re.compile(r"\b[a-zA-Z0-9]+_[a-zA-Z0-9_]+\b")
_FILE_PATH_RE = re.compile(r"\b[a-zA-Z0-9_\-\.\/]+\.[a-zA-Z0-9]{1,4}\b")
_WORD_RE = re.compile(r"\b[a-zA-Z0-9_]{3,}\b")


class QueryAnalysis(NamedTuple):
    """Structured extraction of search terms from an issue."""
    raw_query: str
    expanded_query: str
    exact_identifiers: list[str]
    search_terms: list[str]
    method: str  # "hyde_dense", "llm_expanded", or "deterministic_extraction"
    hypothetical_snippet: Optional[str] = None
    query_vector: Optional[list[float]] = None


def extract_identifiers(text: str) -> list[str]:
    """Extract CamelCase, snake_case, and file paths from text."""
    seen: set[str] = set()
    results: list[str] = []

    for pattern in (_FILE_PATH_RE, _CAMEL_CASE_RE, _SNAKE_CASE_RE):
        for match in pattern.findall(text):
            cleaned = match.strip().rstrip(".,;:)")
            if cleaned and cleaned not in seen and len(cleaned) > 2:
                seen.add(cleaned)
                results.append(cleaned)

    return results


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful alphanumeric keywords, filtering stopwords."""
    words = _WORD_RE.findall(text)
    keywords: list[str] = []
    seen: set[str] = set()

    for w in words:
        w_lower = w.lower()
        if w_lower not in _STOPWORDS and len(w_lower) >= 3 and w_lower not in seen:
            seen.add(w_lower)
            keywords.append(w_lower)

    return keywords


def generate_hyde_code(title: str, body: str = "") -> Optional[str]:
    """
    Generate a hypothetical code snippet solving the issue for HyDE retrieval.
    
    Prompts the model to synthesize a realistic candidate code fix, which is
    subsequently embedded into dense vector space to retrieve analogous code chunks.
    """
    try:
        from app.agents import model_router
        prompt = (
            f"You are a coding agent. Given this technical issue, produce a concise, "
            f"hypothetical code implementation or function patch that resolves it. "
            f"Output ONLY executable code:\n\n"
            f"Title: {title}\n"
            f"Details: {body}\n\n"
            f"Code:"
        )
        response = model_router.complete(prompt, agent_name="retrieval")
        if response and isinstance(response, str) and len(response.strip()) > 15:
            return response.strip()
    except Exception as exc:
        logger.debug("HyDE snippet synthesis fell back to deterministic analysis: %s", exc)
    return None


def try_llm_expand(query: str) -> Optional[str]:
    """
    Attempt to use the shared LLM client to expand code query terms.

    Returns None if the LLM client is unavailable or fails.
    """
    try:
        from app.agents import model_router
        prompt = (
            f"Given this programming issue, provide 3 to 5 candidate file paths, "
            f"function names, or symbols to search for in the repository:\n\n{query}\n\n"
            f"Symbols:"
        )
        response = model_router.complete(prompt, agent_name="retrieval")
        if response and isinstance(response, str):
            return response.strip()
    except Exception as exc:
        logger.debug("LLM query expansion skipped (provider unavailable: %s)", exc)
    return None


def transform_query(title: str, body: str = "", enable_hyde: bool = True) -> QueryAnalysis:
    """
    Produce structured query search terms and HyDE dense embeddings from issue.

    Combines deterministic identifier detection, keyword extraction, and
    Hypothetical Document Embeddings (HyDE) dense vector generation.
    """
    combined = f"{title.strip()}\n{body.strip()}".strip()
    if not combined:
        return QueryAnalysis(
            raw_query="",
            expanded_query="",
            exact_identifiers=[],
            search_terms=[],
            method="deterministic_extraction",
            hypothetical_snippet=None,
            query_vector=None,
        )

    # 1. Deterministic extraction (identifiers + keywords)
    identifiers = extract_identifiers(combined)
    keywords = extract_keywords(combined)

    search_terms: list[str] = []
    seen: set[str] = set()
    for item in identifiers + keywords:
        item_lower = item.lower()
        if item_lower not in seen:
            seen.add(item_lower)
            search_terms.append(item)

    # 2. HyDE (Hypothetical Document Embedding) Attempt
    hypothetical_snippet = None
    query_vector = None
    method = "deterministic_extraction"

    if enable_hyde:
        hypothetical_snippet = generate_hyde_code(title, body)
        if hypothetical_snippet:
            try:
                from app.ml_models.embedding_model import embed, is_embedding_available
                if is_embedding_available():
                    vectors = embed([hypothetical_snippet])
                    if vectors and len(vectors) > 0:
                        query_vector = vectors[0]
                        method = "hyde_dense"
                if method != "hyde_dense":
                    method = "llm_expanded"
            except Exception as e:
                logger.debug("Embedding hypothetical snippet fell back: %s", e)
                method = "llm_expanded"

    # 3. Fallback / complementary symbol expansion if HyDE was not generated
    if not hypothetical_snippet:
        llm_expansion = try_llm_expand(title)
        if llm_expansion:
            method = "llm_expanded"
            combined = f"{combined}\n{llm_expansion}"
            extra_kws = extract_keywords(llm_expansion)
            for kw in extra_kws:
                if kw.lower() not in seen:
                    seen.add(kw.lower())
                    search_terms.append(kw)

    expanded = f"{combined}\n{hypothetical_snippet}" if hypothetical_snippet else combined

    return QueryAnalysis(
        raw_query=combined,
        expanded_query=expanded,
        exact_identifiers=identifiers,
        search_terms=search_terms,
        method=method,
        hypothetical_snippet=hypothetical_snippet,
        query_vector=query_vector,
    )