"""Pure, non-destructive identity projection for Alexa shopping names.

Never mutate Grocy, Alexa, stock, or checkpoints here. The legacy name-based
sync must not consume these projections until a transactional migration exists.
"""
from shopping_sync import normalize, suggest_catalog_matches


class IdentityConflict(ValueError):
    """Two different Alexa entries would map to the same canonical product."""


def preview_identity(alexa_names, products, explicit_choices=None):
    """Return safe identity proposals, reviews and untouched free-text notes.

    Exact catalog matches are safe only when unique; user choices must be
    present in the current candidate set. No remote writes are performed.
    """
    explicit_choices = explicit_choices or {}
    by_id = {int(p["id"]): p for p in products}
    if len(by_id) != len(products):
        raise IdentityConflict("Duplicate Grocy product IDs")
    seen_names = set()
    claimed = {}
    exact, selected, pending, notes = {}, {}, {}, []
    for raw in alexa_names:
        key = normalize(raw)
        if not key or key in seen_names:
            raise IdentityConflict("Empty or duplicate Alexa shopping name")
        seen_names.add(key)
        decision, candidates = suggest_catalog_matches(raw, products)
        choice = explicit_choices.get(key)
        if choice is not None:
            pid = int(choice["product_id"])
            if decision != "review" or pid not in {int(c["id"]) for c in candidates} or pid not in by_id:
                raise IdentityConflict("Stale manual selection")
            target = selected
        elif decision == "exact" and len(candidates) == 1:
            pid = int(candidates[0]["id"])
            target = exact
        elif decision == "review" or decision == "exact":
            pending[key] = candidates
            continue
        else:
            notes.append(raw)
            continue
        if pid in claimed:
            raise IdentityConflict("Multiple Alexa names map to one Grocy product")
        claimed[pid] = key
        target[key] = {"product_id": pid, "canonical_name": by_id[pid]["name"],
                       "original_name": raw}
    return {"exact": exact, "selected": selected, "pending": pending, "notes": notes}
