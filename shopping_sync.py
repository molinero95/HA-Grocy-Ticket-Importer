"""Pure reconciliation planner for Alexa/Grocy shopping lists.

No API writes occur in this module. The caller must persist the returned
baseline only after every proposed operation succeeds. On failure, retry
against freshly fetched snapshots with the previous baseline.
"""
import re
import unicodedata


def normalize(name):
    """Canonical identity for a shopping item; preserve display names."""
    value = unicodedata.normalize("NFKD", str(name or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value).strip().casefold()


def snapshot(names):
    """Return normalized-name -> display-name, rejecting ambiguous duplicates."""
    result = {}
    for name in names:
        key = normalize(name)
        if not key:
            continue
        if key in result:
            raise ValueError("Duplicate normalized item: " + key)
        result[key] = str(name).strip()
    return result


def plan(alexa_names, grocy_names, baseline=None):
    """Plan convergent operations without resurrecting known deletions.

    baseline: previously successfully synchronized normalized names.
    First run uses union, never deletes. Later runs interpret a name
    absent on one side but present in baseline as a deletion, and remove
    it from the other side. A conflicting delete/re-add resolves to
    deletion (fail closed). New names on either side are propagated.
    Completed Alexa items must be excluded by the caller.
    """
    alexa = snapshot(alexa_names)
    grocy = snapshot(grocy_names)
    old = set(baseline or ())
    first_run = baseline is None
    add_alexa, add_grocy, remove_alexa, remove_grocy = [], [], [], []
    for key in sorted(set(alexa) | set(grocy) | old):
        a, g = key in alexa, key in grocy
        if a and g:
            continue
        if key in old and not first_run:
            if a:
                remove_alexa.append(alexa[key])
            if g:
                remove_grocy.append(grocy[key])
        elif a:
            add_grocy.append(alexa[key])
        elif g:
            add_alexa.append(grocy[key])
    next_baseline = (set(alexa) | set(grocy)) - {
        normalize(n) for n in remove_alexa + remove_grocy
    }
    return {
        "add_alexa": add_alexa,
        "add_grocy": add_grocy,
        "remove_alexa": remove_alexa,
        "remove_grocy": remove_grocy,
        "next_baseline": sorted(next_baseline),
    }

# Deliberately conservative: product variants must never be conflated.
_VARIANTS = (
    frozenset(("entera", "semi", "semidesnatada", "desnatada")),
    frozenset(("con lactosa", "sin lactosa")),
    frozenset(("con gluten", "sin gluten")),
    frozenset(("azucar", "sin azucar")),
)

def suggest_catalog_matches(name, products, *, limit=5):
    """Pure, read-only candidate ranking. Never chooses a variant implicitly.

    Returns (decision, candidates), where decision is 'exact', 'review', or
    'unmatched'. Callers must not automatically associate 'review' results.
    """
    from difflib import SequenceMatcher
    query = normalize(name)
    if not query:
        return "unmatched", []
    ranked = []
    for product in products:
        label = normalize(product.get("name"))
        if not label:
            continue
        exact = label == query
        query_words = set(query.split())
        label_words = set(label.split())
        overlap = len(query_words & label_words) / max(len(query_words), len(label_words))
        similarity = SequenceMatcher(None, query, label).ratio()
        # Require substantive common words: string similarity alone can match
        # unrelated short grocery names.
        if not exact and (not query_words & label_words or
                          (overlap < 0.5 and similarity < 0.9 and not query_words.issubset(label_words))):
            continue
        incompatible = False
        for variants in _VARIANTS:
            present_query = {v for v in variants if v in query}
            present_label = {v for v in variants if v in label}
            if present_query and present_label and present_query != present_label:
                incompatible = True
                break
        if incompatible:
            continue
        score = 1.0 if exact else (0.55 * overlap + 0.45 * similarity)
        ranked.append({"id": int(product["id"]), "name": product["name"],
                       "score": round(score, 4), "exact": exact})
    ranked.sort(key=lambda row: (-row["score"], row["name"], row["id"]))
    exact_matches = [row for row in ranked if row["exact"]]
    if len(exact_matches) == 1 and (len(ranked) == 1 or len(query.split()) > 1):
        return "exact", exact_matches
    if ranked:
        return "review", ranked[:limit]
    return "unmatched", []
