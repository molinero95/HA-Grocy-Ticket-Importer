"""Identity-aware, read-only Alexa/Grocy shopping reconciliation planner.

A product identity is its canonical Grocy product ID, not its display name.
Unmatched Alexa text and Grocy notes retain their original free-text identity.
No remote writes, product consolidation or stock changes happen in this module.
"""
from shopping_sync import normalize, snapshot, suggest_catalog_matches


class IdentityConflict(ValueError):
    """An ambiguous or concurrently changed list cannot be synchronized safely."""


def identities(alexa_names, grocy_rows, products, choices=None):
    """Return (Alexa, Grocy) maps keyed by p:<id> or n:<normalized text>.

    grocy_rows are (display_name, raw_shopping_entry) pairs from grocy_entries.
    A manual choice is only a mapping; it never renames an Alexa item or a
    Grocy shopping note. Duplicate identities and orphan products fail closed.
    """
    choices = choices or {}
    by_id = {int(product["id"]): product for product in products}
    if len(by_id) != len(products):
        raise IdentityConflict("Duplicate Grocy product IDs")
    alexa = {}
    alexa_by_name = snapshot(alexa_names)
    for normalized, name in alexa_by_name.items():
        selected = choices.get(normalized)
        if selected is not None:
            pid = int(selected["product_id"])
            if pid not in by_id:
                raise IdentityConflict("Selected product is no longer in Grocy")
            decision, candidates = suggest_catalog_matches(name, products)
            if (decision != "review" or
                    pid not in {int(candidate["id"]) for candidate in candidates}):
                raise IdentityConflict("Selected product is no longer a valid candidate")
            key = "p:" + str(pid)
        else:
            decision, candidates = suggest_catalog_matches(name, products)
            key = ("p:" + str(candidates[0]["id"])
                   if decision == "exact" else "n:" + normalized)
        if key in alexa:
            raise IdentityConflict("Multiple Alexa items resolve to the same identity")
        alexa[key] = {"name": name, "normalized": normalized,
                      "product_id": int(key[2:]) if key.startswith("p:") else None}

    grocy = {}
    grocy_notes = set()
    for name, entry in grocy_rows:
        pid = int(entry.get("product_id") or 0)
        if pid and pid not in by_id:
            raise IdentityConflict("Shopping entry references a missing Grocy product")
        normalized = normalize(name)
        if not normalized:
            raise IdentityConflict("Empty Grocy shopping entry")
        key = "p:" + str(pid) if pid else "n:" + normalized
        if key in grocy:
            raise IdentityConflict("Duplicate Grocy shopping identity")
        if not pid:
            grocy_notes.add(normalized)
        grocy[key] = {"name": name, "product_id": pid or None,
                      "entry_id": int(entry["id"]),
                      "amount": entry.get("amount"),
                      "note": entry.get("note") or ""}
    # A note with the canonical product name is still a note, not a product.
    # Otherwise the first sync could add a duplicate catalog item while
    # retaining the existing shopping note with its original quantity.
    canonical_names = {normalize(by_id[row["product_id"]]["name"])
                       for row in alexa.values() if row["product_id"]}
    if canonical_names & grocy_notes:
        raise IdentityConflict("A Grocy note conflicts with a canonical product")
    # A free-text Grocy note must never be silently replaced by a product.
    # Even an explicit Alexa choice is not permission to delete that note.
    for row in alexa.values():
        if row["product_id"] and row["normalized"] in grocy_notes:
            raise IdentityConflict("A Grocy note conflicts with a selected product")
    return alexa, grocy


def plan_identity(alexa_names, grocy_rows, products, baseline=None, choices=None):
    """Plan additions/deletions using IDs; first run is non-destructive union.

    Baseline is a list of identity keys from a previously verified v2 run.
    A deletion from either side propagates only for identities in baseline.
    """
    alexa, grocy = identities(alexa_names, grocy_rows, products, choices)
    old = set(baseline or ())
    if any(not isinstance(key, str) or
           not (key.startswith("p:") or key.startswith("n:"))
           for key in old):
        raise IdentityConflict("Invalid identity baseline")
    result = {"add_alexa": [], "add_grocy": [],
              "remove_alexa": [], "remove_grocy": []}
    for key in sorted(set(alexa) | set(grocy) | old):
        a, g = alexa.get(key), grocy.get(key)
        if a and g:
            continue
        if baseline is not None and key in old:
            if a:
                result["remove_alexa"].append({"key": key, **a})
            if g:
                result["remove_grocy"].append({"key": key, **g})
        elif a:
            result["add_grocy"].append({"key": key, **a})
        elif g:
            result["add_alexa"].append({"key": key, **g})
    deleted = {row["key"] for action in ("remove_alexa", "remove_grocy")
               for row in result[action]}
    result["next_baseline"] = sorted((set(alexa) | set(grocy)) - deleted)
    return result
