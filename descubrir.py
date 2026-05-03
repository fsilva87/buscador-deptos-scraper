"""
Script de descubrimiento. Se corre UNA vez vía workflow_dispatch
para encontrar los IDs correctos de categoría y comunas.
NO se ejecuta en el cron.
"""
import httpx
import json

BASE = "https://api.mercadolibre.com"

def main():
    out = {}

    # 1) Listar categorías raíz de Chile, buscar "Inmuebles"
    cats = httpx.get(f"{BASE}/sites/MLC/categories", timeout=30).json()
    inmuebles = next((c for c in cats if "inmueble" in c["name"].lower()), None)
    print(f"Categoría inmuebles: {inmuebles}")
    out["inmuebles"] = inmuebles

    # 2) Bajar al árbol de inmuebles, buscar "Departamentos"
    if inmuebles:
        detalle = httpx.get(f"{BASE}/categories/{inmuebles['id']}", timeout=30).json()
        print(f"\nSubcategorías de Inmuebles:")
        for child in detalle.get("children_categories", []):
            print(f"  {child['id']}  {child['name']}")
        out["subcategorias_inmuebles"] = detalle.get("children_categories", [])

    # 3) Búsqueda de prueba: "departamento arriendo providencia"
    r = httpx.get(
        f"{BASE}/sites/MLC/search",
        params={"q": "departamento arriendo providencia", "limit": 3},
        timeout=30,
    ).json()
    print(f"\nBúsqueda de prueba — {r.get('paging', {}).get('total', 0)} resultados totales")
    if r.get("results"):
        item = r["results"][0]
        print(f"  Ejemplo: {item.get('title')}")
        print(f"  Precio: {item.get('price')} {item.get('currency_id')}")
        print(f"  Address: {item.get('location', {}).get('address_line')}")
        print(f"  Atributos disponibles:")
        for a in item.get("attributes", [])[:15]:
            print(f"    - {a.get('id')}: {a.get('name')} = {a.get('value_name')}")
        # Filtros disponibles para refinar
        print(f"\n  Filtros (available_filters):")
        for f in r.get("available_filters", [])[:10]:
            print(f"    - {f.get('id')}: {f.get('name')}")

    out["muestra_busqueda"] = r.get("results", [])[:1]
    with open("debug/descubrimiento.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print("\n✓ debug/descubrimiento.json guardado")

if __name__ == "__main__":
    import os
    os.makedirs("debug", exist_ok=True)
    main()
