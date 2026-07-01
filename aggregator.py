# Status thresholds and values for priority score bucketing
STATUS_THRESHOLD_HIGH = 8.0
STATUS_THRESHOLD_MEDIUM = 5.0

STATUS_WORKING_WELL = "Working well"
STATUS_WORTH_WATCHING = "Worth watching"
STATUS_NEEDS_ATTENTION = "Needs attention"

def score_to_status(score: float) -> str:
    """
    Buckets a priority score into a business-readable plain-language status.
    High Priority (>= 8.0) -> "Working well"
    Medium Priority (>= 5.0) -> "Worth watching"
    Low Priority (< 5.0) -> "Needs attention"
    """
    if score >= STATUS_THRESHOLD_HIGH:
        return STATUS_WORKING_WELL
    elif score >= STATUS_THRESHOLD_MEDIUM:
        return STATUS_WORTH_WATCHING
    else:
        return STATUS_NEEDS_ATTENTION
