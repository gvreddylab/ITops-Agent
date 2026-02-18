def detect_incident_intent(question: str) -> bool:
    q = question.lower()
    return any(w in q for w in ["incident", "issue", "outage", "down", "failure", "degraded", "slowness"])

def extract_incident_fields(question: str) -> dict:
    q = question.lower()
    fields = {}

    # title-ish
    if len(question.strip()) > 8:
        fields["incident_title"] = "present"

    # basic service detection examples (extend later)
    if "core banking" in q:
        fields["affected_service"] = "core banking"
    if "payment" in q:
        fields["affected_service"] = "payment"

    # severity hints
    if "sev1" in q or "critical" in q:
        fields["severity"] = "sev1"
    if "sev2" in q or "high" in q:
        fields["severity"] = "sev2"

    # impact hints
    if "users" in q or "customers" in q:
        fields["number_of_users"] = "mentioned"
    if "impact" in q or "business" in q or "revenue" in q:
        fields["business_impact"] = "mentioned"

    # evidence hints
    if "log" in q or "screenshot" in q or "error" in q or "exception" in q:
        fields["logs_or_screenshots"] = "mentioned"
        fields["error_description"] = "present"

    # time hints
    if "since" in q or "from" in q or "started" in q or "at " in q:
        fields["incident_start_time"] = "mentioned"

    # reporter hints
    if "reported by" in q or "i am" in q:
        fields["reported_by"] = "mentioned"

    return fields
