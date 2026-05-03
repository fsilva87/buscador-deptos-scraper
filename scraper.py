import asyncio
import json
from playwright.async_api import async_playwright

COMUNAS = ["Providencia", "Nunoa", "Penalolen", "Macul", "La-Reina"]

COMUNAS_DISPLAY = {
    "Providencia": "Providencia",
    "Nunoa": "Ñuñoa",
    "Penalolen": "Peñalolén",
    "Macul": "Macul",
    "La-Reina": "La Reina"
}

FILTROS = {
    "min_m2": 80,
    "min_banos": 2,
    "min_estacionamientos": 1,
    "min_piezas": 2,
}

def extraer_numero(attrs, keyword):
    for attr in attrs:
        if keyword.lower() in attr.lower():
            numeros = [int(s) for s in attr.split() if s.isdigit()]
            if numeros:
                return numeros[0]
    return 0

async def scrape_portal(page, comuna_slug, comuna_nombre):
    resultados = []
    url = f"https://www.portalinmobiliario.com/arriendo/departamento/{comuna_slug}-metropolitana"
    print(f"🔍 Scrapeando: {url}")

    try:
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        items = await page.query_selector_all(".ui-search-layout__item")
        print(f"   → Encontrados {len(items)} items en {comuna_nombre}")

        for item in items:
            try:
                title_el = await item.query_selector(".poly-component__title")
                title = await title_el.inner_text() if title_el else "Sin título"

                price_el = await item.query_selector(".poly-price__current")
                price = await price_el.inner_text() if price_el else "Sin precio"

                attrs = await item.query_selector_all(".poly-attributes-list__item")
                attr_texts = []
                for a in attrs:
                    t = await a.inner_text()
                    attr_texts.append(t.strip())

                m2 = extraer_numero(attr_texts, "m²")
                banos = extraer_numero(attr_texts, "baño")
                piezas = extraer_numero(attr_texts, "pieza") or extraer_numero(attr_texts, "dorm")
                estac = extraer_numero(attr_texts, "estac")

                if (
                    m2 >= FILTROS["min_m2"]
                    and banos >= FILTROS["min_banos"]
                    and estac >= FILTROS["min_estacionamientos"]
                    and piezas >= FILTROS["min_piezas"]
                ):
                    link_el = await item.query_selector("a")
                    link = await link_el.get_attribute("href") if link_el else "#"

                    resultados.append({
                        "titulo": title,
                        "precio": price,
                        "comuna": comuna_nombre,
                        "m2": m2,
                        "banos": banos,
                        "piezas": piezas,
                        "estacionamientos": estac,
                        "atributos": attr_texts,
                        "url": link,
                    })

            except Exception as e:
                print(f"   ⚠️ Error en item: {e}")
                continue

    except Exception as e:
        print(f"   ❌ Error scrapeando {comuna_nombre}: {e}")

    return resultados

async def main():
    todos = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for slug, nombre in COMUNAS_DISPLAY.items():
            resultados = await scrape_portal(page, slug, nombre)
            todos.extend(resultados)
            print(f"   ✅ {len(resultados)} deptos válidos en {nombre}")
            await page.wait_for_timeout(2000)

        await browser.close()

    print(f"\n📦 Total departamentos encontrados: {len(todos)}")

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

    print("💾 data.json guardado correctamente")

if __name__ == "__main__":
    asyncio.run(main())
