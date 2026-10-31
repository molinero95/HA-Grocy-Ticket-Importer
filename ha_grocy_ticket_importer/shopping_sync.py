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
