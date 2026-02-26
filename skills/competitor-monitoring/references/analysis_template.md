# Competitive Change Analysis Template

When analyzing a detected change, produce a structured analysis with these sections:

## Analysis JSON Schema

```json
{
  "summary": "One concise sentence describing exactly what changed",
  "impact_assessment": "2-3 sentences on why this matters to our business, our customers, and our market position",
  "actionable_insights": [
    "Specific action we should take in response",
    "Another concrete step (not vague — include who/what/when)"
  ],
  "category": "pricing | product | tech_stack | partnership | content | other",
  "confidence": 0.85
}
```

## Guidelines for Each Field

### summary
- Be specific: "Acme raised Pro plan from $79/mo to $99/mo" not "Acme changed pricing"
- Include numbers when available (price changes, feature counts)
- One sentence maximum

### impact_assessment
- Answer: How does this affect our competitive position?
- Consider: Does this create an opportunity or a threat?
- Think about: customer impact, market perception, strategic implications
- Be honest about significance — not everything is a crisis

### actionable_insights
- Each action should be **specific and executable**
- Bad: "We should monitor this" (vague)
- Good: "Update our comparison page to highlight our $59/mo price advantage"
- Good: "Target Acme Pro customers with a migration offer within 2 weeks"
- Include "poachable" ideas — what are they doing well that we should adopt?
- Limit to 2-4 actions, ranked by impact

### category
Choose the most relevant:
- `pricing` — plan changes, price adjustments, new tiers, discount offers
- `product` — feature additions/removals, UI changes, new capabilities
- `tech_stack` — infrastructure changes, new technologies adopted
- `partnership` — new integrations, partnerships, acquisitions
- `content` — blog posts, marketing changes, positioning shifts
- `other` — anything that doesn't fit above

### confidence
- 0.9+ : Clear, unambiguous change (e.g., explicit price listed)
- 0.7-0.9 : Likely interpretation but some ambiguity
- 0.5-0.7 : Speculative — change is real but significance unclear
- Below 0.5 : Uncertain — flag for human review

## Severity Escalation Criteria

Flag as **CRITICAL** and ensure immediate alert if:
- Competitor launches a direct rival to our core product
- Pricing change undercuts us by >15%
- Acquisition or major strategic partnership announced
- Competitor enters our primary market segment

## Example Analysis

**Input**: Acme Corp pricing page changed — Pro plan price went from $79/mo to $99/mo, Enterprise plan added "AI Features" badge

**Output**:
```json
{
  "summary": "Acme Corp raised Pro plan from $79/mo to $99/mo (+25%) and added 'AI Features' badge to Enterprise tier",
  "impact_assessment": "Acme's Pro tier price increase narrows our price gap — we were $20 cheaper, now we're $40 cheaper at $59/mo. This creates a stronger value proposition for us in the mid-market. The AI features addition to Enterprise signals they're moving upmarket and may deprioritize SMB customers.",
  "actionable_insights": [
    "Update our pricing comparison page to highlight the widened $40/mo gap vs Acme Pro",
    "Run a targeted campaign to Acme Pro users emphasizing our lower price + equivalent features",
    "Investigate what 'AI Features' they added — assess if we need a similar offering for enterprise",
    "Consider if their upmarket move opens opportunity to capture their abandoned SMB segment"
  ],
  "category": "pricing",
  "confidence": 0.95
}
```
