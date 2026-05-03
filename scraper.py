import asyncio
import json
import os
from playwright.async_api import async_playwright

COMUNAS_DISPLAY = {
    "providencia": "Providencia",
    "nunoa": "Ñuñoa",
    "penalolen": "Peñalolén",
    "macul": "Macul",
    "la-reina": "La Reina"
}

FILTROS = {
    "min_m2": 80,
    "min_banos": 2,
    "min_estacionamientos": 1,
    "min_piezas": 2,
}

# Selectores alternativos a probar en paralelo
SELECTORES_ITEM = [
    ".ui-search-layout__item",       # original
    ".ui-search-result",              # fallback ML clásico
    "li.ui-search-layout__item",      # más específico
    "[class*='ui-search-result']",    # comodín
]

os.makedirs("debug", exist_ok=True)

def extraer_numero(attrs, keyword):
    for attr in attrs:
        if keyword.lower() in attr.lower():
            numeros = [int(s) for s in attr.split() if s.isdigit()]
            if numeros:
                return numeros[0]
    return 0

async def scrape_portal(page, comuna_slug, comuna_nombre):
    resultados = []
    items_encontrados = 0
    items_filtrados = 0
    url = (
        "https://www.portalinmobiliario.com/arriendo/"
        f"departamento/{comuna_slug}-metropolitana"
    )
    print(f"\n=== {comuna_nombre} ===")
    print(f"URL: {url}")
    try:
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(6000)  # subido de 4s a 6s

        # DIAGNÓSTICO 1: capturar evidencia
        await page.screenshot(path=f"debug/{comuna_slug}.png", full_page=False)
        html = await page.content()
        with open(f"debug/{comuna_slug}.html", "w", encoding="utf-8") as f:
            f.write(html)
        titulo_pagina = await page.title()
        print(f"   <title>: {titulo_pagina}")
        print(f"   HTML size: {len(html)} chars")

        # DIAGNÓSTICO 2: probar todos los selectores
        items = []
        for sel in SELECTORES_ITEM:
            candidatos = await page.query_selector_all(sel)
            print(f"   selector '{sel}' -> {len(candidatos)} items")
            if candidatos and not items:
                items = candidatos
                print(f"   ✓ usando '{sel}'")

        items_encontrados = len(items)
        if items_encontrados == 0:
            # Pista adicional: ¿hay señales de bot wall?
            for senal in ["captcha", "robot", "verificación", "consent", "cookie"]:
                if senal in html.lower():
                    print(f"   ⚠ posible {senal} detectado en HTML")
            return resultados, 0, 0

        for item in items:
            try:
                title_el = await item.query_selector(".poly-component__title, h2, .ui-search-item__title")
                title = await title_el.inner_text() if title_el else "Sin título"
                price_el = await item.query_selector(".poly-price__current, .price-tag-fraction, .andes-money-amount__fraction")
                price = await price_el.inner_text() if price_el else "Sin precio"
                attrs = await item.query_selector_all(".poly-attributes-list__item, .ui-search-card-attributes__attribute, li")
                attr_texts = [(await a.inner_text()).strip() for a in attrs]

                m2 = extraer_numero(attr_texts, "m²") or extraer_numero(attr_texts, "m2")
                banos = extraer_numero(attr_texts, "baño")
                piezas = (extraer_numero(attr_texts, "pieza")
                          or extraer_numero(attr_texts, "dorm")
                          or extraer_numero(attr_texts, "amb"))
                estac = extraer_numero(attr_texts, "estac") or extraer_numero(attr_texts, "cocher")

                # DIAGNÓSTICO 3: log del primer item por comuna
                if items_filtrados == 0:
                    print(f"   muestra item[0]: m2={m2} banos={banos} piezas={piezas} estac={estac}")
                    print(f"   muestra attrs: {attr_texts[:6]}")

                items_filtrados += 1
                if (m2 >= FILTROS["min_m2"]
                        and banos >= FILTROS["min_banos"]
                        and estac >= FILTROS["min_estacionamientos"]
                        and piezas >= FILTROS["min_piezas"]):
                    link_el = await item.query_selector("a")
                    link = await link_el.get_attribute("href") if link_el else "#"
                    resultados.append({
                        "titulo": title, "precio": price, "comuna": comuna_nombre,
                        "m2": m2, "banos": banos, "piezas": piezas,
                        "estacionamientos": estac, "atributos": attr_texts, "url": link,
                    })
            except Exception as e:
                print(f"   error en item: {e}")
                continue
    except Exception as e:
        print(f"   error scrapeando {comuna_nombre}: {e}")
    return resultados, items_encontrados, items_filtrados

async def main():
    todos = []
    resumen = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-CL",
            timezone_id="America/Santiago",
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()
        for slug, nombre in COMUNAS_DISPLAY.items():
            res, encontrados, parseados = await scrape_portal(page, slug, nombre)
            todos.extend(res)
            resumen.append({
                "comuna": nombre,
                "items_encontrados": encontrados,
                "items_parseados": parseados,
                "items_validos": len(res),
            })
            print(f"   -> {len(res)} válidos / {parseados} parseados / {encontrados} encontrados")
            await page.wait_for_timeout(2000)
        await browser.close()

    print("\n=== RESUMEN ===")
    for r in resumen:
        print(r)
    print(f"TOTAL válidos: {len(todos)}")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)
    with open("debug/resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
