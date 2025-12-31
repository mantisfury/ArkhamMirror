"""LLM prompts for ACH corpus evidence extraction."""

# Evidence extraction from corpus chunks
EVIDENCE_EXTRACTION_PROMPT = """You are an intelligence analyst reviewing document excerpts for evidence relevant to a hypothesis.

HYPOTHESIS: {hypothesis}

DOCUMENT EXCERPTS:
{chunks}

For each excerpt that contains relevant evidence, extract:
1. The exact quote from the text (copy verbatim, use quotation marks)
2. Classification: supports, contradicts, neutral, or ambiguous
3. Brief explanation of relevance (1-2 sentences)

RULES:
- Only use text that ACTUALLY appears in the excerpts - do not paraphrase
- If an excerpt has no relevant evidence, skip it entirely
- Be objective - look for evidence that could support OR contradict the hypothesis
- Mark as "ambiguous" if evidence could reasonably be interpreted multiple ways
- Keep quotes concise but complete enough to understand context

Respond with a JSON array. Example format:
[
  {{
    "chunk_index": 0,
    "quote": "exact text copied from the document",
    "classification": "supports",
    "explanation": "This directly confirms the hypothesis because..."
  }},
  {{
    "chunk_index": 2,
    "quote": "another exact quote from different chunk",
    "classification": "contradicts",
    "explanation": "This suggests an alternative explanation..."
  }}
]

If no relevant evidence is found in any excerpt, respond with an empty array: []
"""

# Batch evidence classification for multiple hypotheses
MULTI_HYPOTHESIS_CLASSIFICATION_PROMPT = """You are an intelligence analyst evaluating how a piece of evidence relates to multiple hypotheses.

EVIDENCE:
"{evidence_text}"

HYPOTHESES:
{hypotheses}

For each hypothesis, classify how this evidence relates to it:
- "supports" - Evidence makes this hypothesis more likely
- "contradicts" - Evidence makes this hypothesis less likely
- "neutral" - Evidence has no bearing on this hypothesis
- "ambiguous" - Evidence could be interpreted either way

Respond with JSON:
{{
  "classifications": [
    {{
      "hypothesis_index": 0,
      "classification": "supports|contradicts|neutral|ambiguous",
      "explanation": "Brief reason for this classification"
    }}
  ]
}}
"""

# Hypothesis discovery from corpus themes
HYPOTHESIS_DISCOVERY_PROMPT = """You are an intelligence analyst identifying possible hypotheses based on document evidence.

FOCUS QUESTION: {question}

RELEVANT DOCUMENT EXCERPTS:
{chunks}

Based on these documents, identify 3-5 distinct hypotheses that could answer the focus question.

Requirements:
- Each hypothesis should be testable and specific
- Hypotheses should be mutually exclusive where possible
- Ground hypotheses in actual themes/facts from the documents
- Include both likely and alternative explanations

Respond with JSON:
{{
  "hypotheses": [
    {{
      "title": "Short hypothesis title",
      "description": "Fuller explanation of this hypothesis",
      "supporting_evidence": "Quote or reference from documents that suggests this"
    }}
  ]
}}
"""

# Contradiction detection between documents
CONTRADICTION_DETECTION_PROMPT = """You are an intelligence analyst looking for contradictions in documentary evidence.

DOCUMENT EXCERPTS:
{chunks}

CONTEXT: These excerpts are being analyzed for the question: "{question}"

Identify any contradictions or conflicting claims between different documents/excerpts:
- Direct contradictions (Document A says X, Document B says not-X)
- Inconsistencies in timelines, facts, or claims
- Different sources making incompatible assertions

Respond with JSON:
{{
  "contradictions": [
    {{
      "excerpt_a_index": 0,
      "excerpt_b_index": 3,
      "quote_a": "Exact quote from first excerpt",
      "quote_b": "Exact quote from second excerpt",
      "nature": "Brief description of the contradiction",
      "significance": "low|medium|high"
    }}
  ]
}}

If no contradictions found, respond with: {{"contradictions": []}}
"""

# Evidence rating suggestions based on corpus context
CORPUS_RATING_PROMPT = """You are an intelligence analyst rating how evidence relates to a hypothesis.

HYPOTHESIS: {hypothesis}

EVIDENCE FROM CORPUS:
Quote: "{quote}"
Source: {source}
Page: {page}

Additional context from same document:
{context}

Rate the consistency of this evidence with the hypothesis using:
- "++" (Highly Consistent) - Strong direct support
- "+" (Consistent) - Moderate support
- "N" (Neutral) - No clear relationship
- "-" (Inconsistent) - Moderate contradiction
- "--" (Highly Inconsistent) - Strong contradiction

Respond with JSON:
{{
  "rating": "++|+|N|-|--",
  "reasoning": "Explanation for this rating",
  "caveats": "Any important qualifications or uncertainties"
}}
"""
