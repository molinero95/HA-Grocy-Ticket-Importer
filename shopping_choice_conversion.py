"""Explicitly selected note-to-product conversion without duplicate shopping rows."""
from decimal import Decimal
from shopping_sync import normalize
from shopping_identity_sync import IdentityConflict


def _default_rows(grocy):
    from shopping_sync_adapters import _grocy_done
    rows = grocy("GET", "objects/shopping_list")
    if not isinstance(rows, list):
        raise ValueError("No se pudo verificar la lista de Grocy")
    return [row for row in rows if int(row.get("shopping_list_id") or 1) == 1
            and not _grocy_done(row.get("done"))]


def manual_choice(grocy, queue, path, key, product_id, operation_id=None):
    """Materialize an explicit choice now; no Alexa or stock writes, no increment."""
    import uuid
    from stock_commands import execute_once
    entry = next((row for row in queue.pending(path) if row["key"] == normalize(key)), None)
    if entry is None or entry.get("removed"):
        raise ValueError("La propuesta ya no está disponible; actualiza la lista")
    # Older v1 callers receive the same durable command for this review episode.
    operation_id = operation_id or str(uuid.uuid5(uuid.NAMESPACE_URL,
        f"{path}:{entry['key']}:{entry.get('generation', 1)}:choose:{product_id}"))

    # Validate known conflicts before recording a possibly dispatched command.
    from shopping_sync import suggest_catalog_matches
    from shopping_sync_adapters import _grocy_done
    products = grocy("GET", "objects/products")
    if not isinstance(products, list):
        raise ValueError("No se pudo verificar el catálogo de Grocy")
    products = [p for p in products if _grocy_done(p.get("active", True))]
    rows = _default_rows(grocy)
    queue.refresh_catalog(path, products, [r.get("note") or "" for r in rows if not r.get("product_id")])
    entry = next(row for row in queue.pending(path) if row["key"] == entry["key"])
    attached = next((row for row in rows if int(row["id"]) == entry.get("shopping_entry_id")), None)
    if attached and attached.get("product_id") and product_id and int(attached["product_id"]) != product_id:
        raise ValueError("El artículo ya está asociado a otro producto. Quita esa fila antes de elegir uno nuevo.")
    product = next((p for p in products if int(p["id"]) == product_id), None)
    if product_id:
        decision, candidates = suggest_catalog_matches(entry["name"], products)
        created_choice = product_id == entry.get('created_product_id')
        if (product is None or (not created_choice and ((decision != "review" and not (decision == "exact" and entry.get("requires_product")))
                or product_id not in {int(p["id"]) for p in candidates}))
                or product_id not in {int(p["id"]) for p in entry["candidates"]}):
            raise ValueError("La sugerencia ha cambiado; actualiza la lista")
    elif entry.get("requires_product"):
        raise ValueError("Asocia la nota a su producto o quita únicamente el artículo original de la lista")
    notes = [r for r in rows if not r.get("product_id") and normalize(r.get("note") or "") == entry["key"]]
    canonical = [r for r in rows if product_id and int(r.get("product_id") or 0) == product_id]
    if len(notes) > 1 or len(canonical) > 1 or (notes and canonical):
        raise ValueError("El producto elegido ya está en la lista o hay notas duplicadas. Quita el original o elige otro producto.")
    if not product_id and entry.get("shopping_entry_id") and entry.get("selected_product_id"):
        raise ValueError("El artículo ya está asociado; actualiza la lista")

    def apply():
        if notes:
            original = notes[0]
            if product_id:
                _, operations = project_choices([(entry["name"], original)], products,
                                                 {entry["key"]: {"product_id": product_id}})
                apply_choices(grocy, operations)
        elif not canonical:
            payload = {"shopping_list_id": 1, "note": entry["name"], "amount": 1}
            if product_id:
                payload.update(product_id=product_id, qu_id=int(product["qu_id_stock"]))
            grocy("POST", "objects/shopping_list", payload)
        saved = [r for r in _default_rows(grocy) if
                 (int(r.get("product_id") or 0) == product_id if product_id else
                  not r.get("product_id") and normalize(r.get("note") or "") == entry["key"])]
        if len(saved) != 1:
            raise RuntimeError("No se pudo verificar la elección; comprueba la lista antes de reintentar")
        if product_id:
            queue.choose(path, entry["key"], product_id)
        else:
            queue.keep_original(path, entry["key"])
        queue.attach_entry(path, entry["key"], saved[0]["id"])
        return {"ok": True, "item_id": int(saved[0]["id"])}

    return execute_once(operation_id, {"kind": "manual-shopping-choice", "scope": str(path),
                                     "key": entry["key"], "product_id": product_id}, apply)


def delete_verified(grocy, original):
    """An idempotent deletion may continue only while the exact observed row matches."""
    rows = grocy("GET", "objects/shopping_list")
    current = next((r for r in rows if int(r["id"]) == int(original["id"])), None)
    if current is None:
        return
    fields = ("id", "product_id", "shopping_list_id", "amount", "note", "done", "qu_id")
    if any(str(current.get(field)) != str(original.get(field)) for field in fields):
        raise ValueError("El artículo ha cambiado; actualiza la lista antes de quitarlo")
    if int(current.get("shopping_list_id") or 1) != 1:
        raise ValueError("El artículo pertenece a otra lista")
    grocy("DELETE", f"objects/shopping_list/{int(original['id'])}")
    if any(int(r["id"]) == int(original["id"]) for r in grocy("GET", "objects/shopping_list")):
        raise RuntimeError("No se pudo confirmar la eliminación")


def remove_pending(grocy, queue, path, key):
    entry = next((row for row in queue.pending(path) if row["key"] == normalize(key)), None)
    if entry is None:
        raise ValueError("La propuesta ya no está disponible; actualiza la lista")
    rows = _default_rows(grocy)
    matching = [r for r in rows if (entry.get("shopping_entry_id") == int(r["id"]) or
                (not r.get("product_id") and normalize(r.get("note") or "") == entry["key"]))]
    if len(matching) > 1:
        raise ValueError("Hay artículos duplicados; actualiza la lista")
    original = matching[0] if matching else entry.get("removal")
    queue.stage_removal(path, entry["key"], original)
    if original:
        delete_verified(grocy, original)
    return {"ok": True}


def project_choices(rows, products, choices):
    catalog = {int(p["id"]): p for p in products}
    projected, operations = [], []
    existing = {int(row.get("product_id") or 0) for _, row in rows}
    for name, row in rows:
        choice = choices.get(normalize(name))
        if not choice or int(row.get("product_id") or 0):
            projected.append((name, row))
            continue
        pid = int(choice["product_id"])
        if pid not in catalog or pid in existing:
            raise IdentityConflict("A selected product already has a shopping entry")
        amount = Decimal(str(row["amount"]))
        if not amount.is_finite() or amount <= 0:
            raise IdentityConflict("Invalid shopping note quantity")
        target = {**row, "product_id": pid, "qu_id": int(catalog[pid]["qu_id_stock"])}
        projected.append((str(catalog[pid]["name"]), target))
        operations.append((row, target))
        existing.add(pid)
    return projected, operations


def apply_choices(grocy, operations):
    for original, target in operations:
        row_id = int(original["id"])
        current = grocy("GET", f"objects/shopping_list/{row_id}")
        fields = ("id", "product_id", "shopping_list_id", "amount", "note", "done", "qu_id")
        if any(str(current.get(key)) != str(original.get(key)) for key in fields):
            raise IdentityConflict("Shopping note changed before explicit association")
        grocy("PUT", f"objects/shopping_list/{row_id}", {"product_id": target["product_id"], "qu_id": target["qu_id"]})
        saved = grocy("GET", f"objects/shopping_list/{row_id}")
        if (int(saved.get("product_id") or 0) != target["product_id"]
                or Decimal(str(saved["amount"])) != Decimal(str(original["amount"]))
                or saved.get("note") != original.get("note")
                or int(saved.get("shopping_list_id") or 1) != 1):
            raise IdentityConflict("Explicit shopping association could not be verified")
