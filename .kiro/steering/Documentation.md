---
inclusion: fileMatch
fileMatchPattern: '**/*.md'
---
# Documentation Spec (Diátaxis)

This spec defines how to write documentation using the Diátaxis framework. It also sets language and style rules that avoid common AI markers so the writing reads like a careful human author.

## 1) Diátaxis intent and scope

Write four distinct doc types. Do not mix them.

- Tutorials (learning)
  - Goal: build confidence by doing.
  - Scope: a single, friendly walkthrough with a clear end result.
  - Voice: encouraging, patient, light.

- How-to guides (task)
  - Goal: help someone get a job done.
  - Scope: focused, minimal background, ordered steps.
  - Voice: direct and practical.

- Reference (lookup)
  - Goal: provide exact facts.
  - Scope: complete, structured, no narrative.
  - Voice: neutral, precise, terse.

- Explanations (understanding)
  - Goal: build mental models and context.
  - Scope: concepts, trade-offs, rationale, history.
  - Voice: thoughtful, reflective, but grounded.

If content overlaps, split it into separate docs rather than blending styles.

## 2) Structure requirements

- Start each doc with a clear purpose line: who it is for and what it covers.
- Use headings that match the doc type (examples below).
- Keep sections short and logically ordered.
- Prefer short paragraphs over long blocks.
- Put prerequisites up front if needed.
- Examples should be realistic and minimal.
- Include a `doc_type: tutorial|how-to|reference|explanation` line near the top (front matter or first 60 lines).

### Suggested structures

Tutorials
1. Outcome
2. Prerequisites
3. Step-by-step walkthrough
4. Check your work
5. Next steps

How-to guides
1. Task summary
2. Prerequisites
3. Steps
4. Troubleshooting (if common)

Reference
1. Overview (one paragraph)
2. Definitions
3. Syntax / inputs / outputs
4. Behaviors and edge cases
5. Examples

Explanations
1. Concept summary
2. Why this works
3. Trade-offs and alternatives
4. Common misconceptions

## 3) Language and tone (human-first)

Avoid patterns that sound machine-generated or overly polished. Write like a senior engineer explaining a real system.

Do:
- Use concrete verbs and specific nouns.
- Prefer short, plain sentences.
- Vary sentence length occasionally.
- Use contractions sparingly when it fits the voice.
- Keep claims modest and testable.

Avoid:
- Overly generic transitions ("Furthermore", "Moreover", "In conclusion").
- Empty confidence ("It is important to note", "It should be noted").
- Vague promises ("seamless", "robust", "powerful", "cutting-edge").
- Overuse of bullet lists when a paragraph is clearer.
- Excessive symmetry or repetitive phrasing.

## 4) Anti-AI markers checklist

Before finalizing, check for these and rewrite:

- Repeated sentence templates ("This section will", "In this section").
- Overly balanced pros/cons that read like a template.
- Generic filler ("best practices", "leveraging", "utilize").
- Reassuring tone without evidence ("This makes it easy").
- Long, abstract introductions that delay the real content.

## 5) Precision and evidence

- If you claim a behavior, back it with a fact, example, or a pointer to the source.
- If a detail is unknown, say so and explain how to verify.
- Prefer measurable language over superlatives.

## 6) Examples and commands

- Use real paths, filenames, and outputs when possible.
- Annotate commands only when the meaning is not obvious.
- Keep examples short and focused on the point.

## 7) Consistency rules

- Use the same term for the same thing throughout a doc.
- Expand acronyms on first use unless the audience is expert.
- Keep capitalization consistent for commands, flags, and UI labels.
- Match code style to the project (format, naming, casing).

## 8) Review pass

Do one final pass with these questions:

- Is the doc type obvious from the first paragraph?
- Does it do one job well, without drifting?
- Are steps or facts ordered the way someone would use them?
- Does the tone feel like a colleague wrote it?

## 9) Enterprise and regulated environments

Use this appendix when writing for regulated contexts (finance, healthcare, government) or large enterprises.

- Tie decisions to policy: cite control IDs, standards, and internal requirements.
- Make compliance auditable: list evidence locations (logs, tickets, change records) and how to reproduce checks.
- Define boundaries: document data flows, trust zones, and responsibility splits.
- Surface mandatory controls: encryption, retention, key management, approvals, and data residency.
- Be precise about risk: name the risk, impact, likelihood, and mitigation.
- Document reversibility: rollback paths, decommission steps, and data deletion or archival.
- Use the standards' language: align with SOC 2, ISO 27001, HIPAA, PCI, or local equivalents.
- Separate policy from implementation: link to the policy, then describe how the system satisfies it.
- Include operational guardrails: runbooks, escalation paths, and incident response hooks.
- Call out third-party dependencies: contracts, SLAs, and compliance posture.
