"""
Confirmed research tags (#139).

session["confirmed_tags"] entries are {"value": str, "origin": "ai" |
"user"} so the UI can show which tags came from Scilene's suggestions
vs. what a researcher typed themselves ("remain visually
distinguishable from AI-generated tags"). The recommender never sees
`origin` -- only `.value` ever reaches search execution
(confirmed_tag_values() below), matching the existing rule that once a
tag is confirmed it's indistinguishable to the recommendation engine
(docs/RESEARCH_INTERPRETER.md) -- the AI/USER distinction is purely a
display concern layered on top, not a new signal into scoring.

"ai" covers anything Scilene itself proposed and the user then
confirmed (accepted Research Interpreter suggestions, selected
Detected Research Areas, Research Idea Assistant keywords) -- all of
these are already presented to the user as Scilene's own suggestions
elsewhere in the UI, even where the underlying logic is deterministic
rather than a model call. "user" covers anything typed directly: the
manual "Add a tag" field (also the only tag entry point in the
no-abstract "idea" mode -- #143), #102's "add a missing discipline"
field, and an imported .sls (or legacy .jis) session's tags.
"""


def add_confirmed_tag(session, value, origin):
    value = (value or "").strip()
    if not value:
        return
    tags = session.setdefault("confirmed_tags", [])
    if not any(t["value"] == value for t in tags):
        tags.append({"value": value, "origin": origin})


def confirmed_tag_values(session):
    return [t["value"] for t in session.get("confirmed_tags", [])]
