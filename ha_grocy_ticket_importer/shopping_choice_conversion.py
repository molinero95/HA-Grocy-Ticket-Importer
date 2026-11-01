"""Explicitly selected note-to-product conversion without duplicate shopping rows."""
from decimal import Decimal
from shopping_sync import normalize
from shopping_identity_sync import IdentityConflict


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
