"""Read-only Grocy merge dependency audit.

Every unsupported or unavailable collection is an explicit blocker. This module
never changes product IDs, stock, shopping lists or history.
"""
from decimal import Decimal, InvalidOperation

COLLECTIONS = (
    ("shopping_list", "Lista de la compra"),
    ("recipes_pos", "Ingredientes de recetas"),
    ("chores", "Tareas"),
    ("product_barcodes", "Códigos de barras"),
    ("quantity_unit_conversions", "Conversiones de unidades"),
    ("product_groups", "Grupos de productos"),
)
REFERENCES = ("product_id", "product_id1", "product_id2", "product_id_to", "product_id_from")


def audit_merge(grocy, source, target):
    ids = {int(source["id"]), int(target["id"])}
    findings = []
    for collection, label in COLLECTIONS:
        try:
            rows = grocy("GET", "objects/" + collection)
            if not isinstance(rows, list):
                raise ValueError("Respuesta inesperada")
            refs = [
                {"id": row.get("id"), "product_id": row.get("product_id"), "field": field}
                for row in rows if isinstance(row, dict)
                for field in REFERENCES
                if str(row.get(field, "")) in {str(x) for x in ids}
            ]
            findings.append({"collection": collection, "label": label,
                             "status": "ok", "references": refs, "count": len(refs)})
        except Exception:
            findings.append({"collection": collection, "label": label,
                             "status": "unavailable", "references": [], "count": None})
    blockers = []
    if source["unit_id"] != target["unit_id"]:
        blockers.append("Las unidades de stock son diferentes")
    if source.get("purchase_unit_id") != target.get("purchase_unit_id") or source["pack_size"] != target["pack_size"]:
        blockers.append("Las unidades de compra o factores de envase son diferentes")
    for product in (source, target):
        try:
            stock = Decimal(str(product["stock_amount"]))
            if not stock.is_finite() or stock < 0:
                raise InvalidOperation()
            if stock:
                blockers.append("Existen unidades en stock: hay que conciliar movimientos y lotes")
                break
        except (InvalidOperation, ValueError, TypeError):
            blockers.append("No se puede verificar el stock")
            break
    for finding in findings:
        if finding["status"] != "ok":
            blockers.append("No se pudo auditar: " + finding["label"])
        elif finding["count"]:
            blockers.append("Hay referencias que requieren migración: " + finding["label"])
    blockers.append("Historial, lotes, precios, tickets y referencias externas no auditados exhaustivamente")
    return {"collections": findings, "blockers": blockers, "can_merge": False}
