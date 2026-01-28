"""
Mode Switching and Auto-Escalation for Cortex Activator

This module implements Phase 4 of the adaptive intelligence system:
1. Query Complexity Scoring - Determines how complex a query is
2. LLM ↔ Agent Mode Detection - Decides if query needs agent capabilities
3. Auto-Escalation Logic - Escalates to more capable modes when needed

Mode Types:
    - LLM: Simple query-response (can be handled by LLM directly)
    - AGENT: Requires tool execution, multi-step reasoning, or state management
    - HYBRID: Needs both LLM reasoning AND tool execution

Complexity Levels:
    - SIMPLE: Direct tool call, single operation
    - MODERATE: Multiple operations, requires context
    - COMPLEX: Multi-step reasoning, investigation, analysis
    - EXPERT: Requires human escalation or specialized knowledge

Auto-Escalation Triggers:
    - Low confidence from routing
    - Previous similar queries failed
    - Explicit complexity indicators
    - Timeout or failure in simpler mode
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple

import structlog

log = structlog.get_logger()


# =============================================================================
# Enums
# =============================================================================

class QueryMode(str, Enum):
    """Execution mode for a query."""
    LLM = "llm"          # Direct LLM response, no tools
    AGENT = "agent"      # Agent with tool execution
    HYBRID = "hybrid"    # LLM reasoning + tool execution


class ComplexityLevel(str, Enum):
    """Query complexity level."""
    SIMPLE = "simple"        # Score 0-25
    MODERATE = "moderate"    # Score 26-50
    COMPLEX = "complex"      # Score 51-75
    EXPERT = "expert"        # Score 76-100


class EscalationReason(str, Enum):
    """Why a query was escalated."""
    LOW_CONFIDENCE = "low_confidence"
    PREVIOUS_FAILURE = "previous_failure"
    EXPLICIT_COMPLEXITY = "explicit_complexity"
    MULTI_STEP = "multi_step"
    INVESTIGATION = "investigation"
    TIMEOUT = "timeout"
    ERROR = "error"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ComplexityScore:
    """Result of complexity analysis."""
    score: int  # 0-100
    level: ComplexityLevel
    factors: dict[str, int]  # Individual factor scores
    reasoning: str


@dataclass
class ModeDecision:
    """Result of mode detection."""
    mode: QueryMode
    complexity: ComplexityScore
    confidence: float  # 0.0-1.0
    escalation_reason: Optional[EscalationReason] = None
    recommended_model: Optional[str] = None  # haiku, sonnet, opus


# =============================================================================
# Complexity Scoring
# =============================================================================

# Complexity indicators with weights
COMPLEXITY_PATTERNS = {
    # High complexity (add 15-25 points)
    "investigate": (r"\b(investigate|figure out|find out why)\b", 20),
    "analyze": (r"\b(analyze|examine|assess|evaluate)\b", 18),
    "troubleshoot": (r"\b(troubleshoot|debug|diagnose|fix)\b", 22),
    "explain_why": (r"\b(explain why|why (is|are|does|do|did|was))\b", 15),
    "multi_step": (r"\b(first.*then|after.*do|step by step)\b", 18),
    "compare": (r"\b(compare|difference between|versus|vs\.?)\b", 15),

    # Moderate complexity (add 8-14 points)
    "what_is": (r"\b(what (is|are|was|were))\b", 8),
    "how_to": (r"\b(how (to|do|can|should))\b", 10),
    "configure": (r"\b(configure|setup|set up|enable|disable)\b", 12),
    "multiple_items": (r"\b(all|every|each|multiple|several)\b", 10),
    "conditional": (r"\b(if|when|unless|only when)\b", 12),

    # Low complexity indicators (negative points)
    "list_show": (r"\b(list|show|get|display)\b", -5),
    "simple_action": (r"\b(restart|reboot|block|unblock)\b", -8),
    "status_check": (r"\b(status|health|check if)\b", -5),
}

# Length-based complexity
LENGTH_SCORES = [
    (20, -10),    # Very short queries are likely simple
    (50, -5),     # Short queries slightly simpler
    (100, 0),     # Medium length is baseline
    (200, 5),     # Longer queries slightly more complex
    (500, 15),    # Long queries more complex
    (1000, 25),   # Very long queries likely complex
]


def score_complexity(query: str, context: Optional[dict] = None) -> ComplexityScore:
    """
    Score the complexity of a query from 0-100.

    Factors considered:
    - Pattern matching for complexity indicators
    - Query length
    - Context size
    - Question count
    - Entity/number count
    """
    score = 50  # Start at baseline
    factors = {}
    query_lower = query.lower()

    # Pattern-based scoring
    for name, (pattern, weight) in COMPLEXITY_PATTERNS.items():
        if re.search(pattern, query_lower):
            factors[name] = weight
            score += weight

    # Length-based scoring
    length = len(query)
    length_adjustment = 0
    for threshold, adjustment in LENGTH_SCORES:
        if length <= threshold:
            length_adjustment = adjustment
            break
    else:
        length_adjustment = 30  # Very long queries
    factors["length"] = length_adjustment
    score += length_adjustment

    # Question count (multiple questions = more complex)
    question_count = query.count("?")
    if question_count > 1:
        question_adjustment = (question_count - 1) * 8
        factors["questions"] = question_adjustment
        score += question_adjustment

    # Context complexity
    if context:
        context_size = len(str(context))
        if context_size > 500:
            factors["context"] = 10
            score += 10
        if context_size > 2000:
            factors["context"] = 20
            score += 10  # Additional 10

    # Number of entities mentioned (devices, clients, networks, etc.)
    entity_patterns = [
        r"\b[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}",  # MAC addresses
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",  # IP addresses
        r"\bvlan[- ]?\d+\b",  # VLANs
        r"\b[a-z]+-[a-z]+-\d+\b",  # Device names like ap-office-01
    ]
    entity_count = sum(len(re.findall(p, query_lower)) for p in entity_patterns)
    if entity_count > 2:
        factors["entities"] = entity_count * 3
        score += entity_count * 3

    # Clamp to 0-100
    score = max(0, min(100, score))

    # Determine level
    if score <= 25:
        level = ComplexityLevel.SIMPLE
    elif score <= 50:
        level = ComplexityLevel.MODERATE
    elif score <= 75:
        level = ComplexityLevel.COMPLEX
    else:
        level = ComplexityLevel.EXPERT

    # Generate reasoning
    top_factors = sorted(factors.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
    factor_desc = ", ".join(f"{k}({v:+d})" for k, v in top_factors if v != 0)
    reasoning = f"Score {score} ({level.value}): {factor_desc}"

    return ComplexityScore(
        score=score,
        level=level,
        factors=factors,
        reasoning=reasoning
    )


# =============================================================================
# Mode Detection
# =============================================================================

# Agent mode indicators
AGENT_PATTERNS = [
    r"\b(execute|run|perform|do|make)\b.*\b(command|operation|action)\b",
    r"\b(change|modify|update|delete|create|add|remove)\b",
    r"\b(restart|reboot|reset|reload)\b",
    r"\b(block|unblock|enable|disable)\b",
    r"\b(configure|setup|set)\b.*\b(to|as|with)\b",
]

# LLM-only indicators
LLM_PATTERNS = [
    r"^(what|who|where|when|which)\b.*\?$",
    r"\b(explain|describe|tell me about)\b",
    r"\b(how does|what does|why does)\b.*\b(work|mean)\b",
    r"\b(summarize|summary of)\b",
]


def detect_mode(
    query: str,
    complexity: ComplexityScore,
    previous_confidence: Optional[float] = None,
    previous_success: Optional[bool] = None
) -> ModeDecision:
    """
    Detect the appropriate execution mode for a query.

    Decision factors:
    - Query content patterns
    - Complexity score
    - Previous routing confidence
    - Previous execution success
    """
    query_lower = query.lower()
    confidence = 0.8  # Start with reasonable confidence
    escalation_reason = None

    # Check for agent indicators
    is_agent_query = any(re.search(p, query_lower) for p in AGENT_PATTERNS)
    is_llm_query = any(re.search(p, query_lower) for p in LLM_PATTERNS)

    # Base mode decision
    if is_agent_query and is_llm_query:
        mode = QueryMode.HYBRID
        confidence = 0.75
    elif is_agent_query:
        mode = QueryMode.AGENT
        confidence = 0.85
    elif is_llm_query:
        mode = QueryMode.LLM
        confidence = 0.85
    else:
        # Default based on complexity
        if complexity.level == ComplexityLevel.SIMPLE:
            mode = QueryMode.AGENT
            confidence = 0.7
        elif complexity.level in (ComplexityLevel.COMPLEX, ComplexityLevel.EXPERT):
            mode = QueryMode.HYBRID
            confidence = 0.6
        else:
            mode = QueryMode.AGENT  # Default to agent for network queries
            confidence = 0.75

    # Escalation checks
    if previous_confidence is not None and previous_confidence < 0.5:
        escalation_reason = EscalationReason.LOW_CONFIDENCE
        if mode == QueryMode.LLM:
            mode = QueryMode.AGENT
        elif mode == QueryMode.AGENT:
            mode = QueryMode.HYBRID
        confidence = max(0.3, confidence - 0.2)

    if previous_success is False:
        escalation_reason = EscalationReason.PREVIOUS_FAILURE
        if mode == QueryMode.AGENT:
            mode = QueryMode.HYBRID
        confidence = max(0.3, confidence - 0.3)

    if complexity.level == ComplexityLevel.EXPERT:
        escalation_reason = EscalationReason.EXPLICIT_COMPLEXITY
        mode = QueryMode.HYBRID
        confidence = max(0.4, confidence - 0.1)

    # Multi-step detection
    if "multi_step" in complexity.factors:
        escalation_reason = EscalationReason.MULTI_STEP
        if mode == QueryMode.LLM:
            mode = QueryMode.AGENT
        confidence = max(0.5, confidence - 0.1)

    # Investigation queries need hybrid mode
    if "investigate" in complexity.factors or "troubleshoot" in complexity.factors:
        escalation_reason = EscalationReason.INVESTIGATION
        mode = QueryMode.HYBRID
        confidence = 0.7

    # Recommend model based on complexity
    if complexity.score <= 30:
        recommended_model = "haiku"
    elif complexity.score <= 60:
        recommended_model = "sonnet"
    else:
        recommended_model = "opus"

    return ModeDecision(
        mode=mode,
        complexity=complexity,
        confidence=confidence,
        escalation_reason=escalation_reason,
        recommended_model=recommended_model
    )


# =============================================================================
# Auto-Escalation Logic
# =============================================================================

@dataclass
class EscalationContext:
    """Context for escalation decision."""
    query: str
    current_mode: QueryMode
    attempt_count: int = 1
    last_error: Optional[str] = None
    last_latency_ms: Optional[int] = None
    similar_query_success_rate: Optional[float] = None


def should_escalate(ctx: EscalationContext) -> Tuple[bool, Optional[QueryMode], Optional[EscalationReason]]:
    """
    Determine if the query should be escalated to a more capable mode.

    Returns:
        (should_escalate, new_mode, reason)
    """
    # Don't escalate beyond hybrid
    if ctx.current_mode == QueryMode.HYBRID and ctx.attempt_count > 2:
        return False, None, None

    # Escalate on error
    if ctx.last_error:
        if "timeout" in ctx.last_error.lower():
            reason = EscalationReason.TIMEOUT
        else:
            reason = EscalationReason.ERROR

        if ctx.current_mode == QueryMode.LLM:
            return True, QueryMode.AGENT, reason
        elif ctx.current_mode == QueryMode.AGENT:
            return True, QueryMode.HYBRID, reason
        return False, None, None

    # Escalate on high latency (>30s for agent, >60s for hybrid)
    if ctx.last_latency_ms:
        latency_threshold = 30000 if ctx.current_mode == QueryMode.AGENT else 60000
        if ctx.last_latency_ms > latency_threshold:
            if ctx.current_mode == QueryMode.AGENT:
                return True, QueryMode.HYBRID, EscalationReason.TIMEOUT

    # Escalate on low success rate for similar queries
    if ctx.similar_query_success_rate is not None and ctx.similar_query_success_rate < 0.5:
        if ctx.current_mode == QueryMode.LLM:
            return True, QueryMode.AGENT, EscalationReason.PREVIOUS_FAILURE
        elif ctx.current_mode == QueryMode.AGENT:
            return True, QueryMode.HYBRID, EscalationReason.PREVIOUS_FAILURE

    return False, None, None


# =============================================================================
# Unified Analysis Function
# =============================================================================

def analyze_query(
    query: str,
    context: Optional[dict] = None,
    previous_confidence: Optional[float] = None,
    previous_success: Optional[bool] = None,
    similar_success_rate: Optional[float] = None
) -> ModeDecision:
    """
    Perform full query analysis including complexity scoring and mode detection.

    This is the main entry point for Phase 4 features.

    Args:
        query: The user query
        context: Optional context dict
        previous_confidence: Confidence from a previous routing attempt
        previous_success: Whether a previous attempt succeeded
        similar_success_rate: Success rate of similar past queries

    Returns:
        ModeDecision with mode, complexity, confidence, and recommendations
    """
    # Score complexity
    complexity = score_complexity(query, context)

    # Detect mode
    decision = detect_mode(query, complexity, previous_confidence, previous_success)

    # Additional escalation check based on similar query success rate
    if similar_success_rate is not None and similar_success_rate < 0.6:
        # Lower confidence and potentially escalate
        decision.confidence = max(0.3, decision.confidence - 0.2)
        if decision.mode == QueryMode.AGENT and similar_success_rate < 0.4:
            decision = ModeDecision(
                mode=QueryMode.HYBRID,
                complexity=decision.complexity,
                confidence=decision.confidence,
                escalation_reason=EscalationReason.PREVIOUS_FAILURE,
                recommended_model=decision.recommended_model
            )

    log.debug(
        "query_analyzed",
        complexity_score=complexity.score,
        complexity_level=complexity.level.value,
        mode=decision.mode.value,
        confidence=round(decision.confidence, 2),
        escalation=decision.escalation_reason.value if decision.escalation_reason else None,
        recommended_model=decision.recommended_model
    )

    return decision
