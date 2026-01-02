import pymupdf  # PyMuPDF (v1.24+ uses 'pymupdf' instead of 'fitz')
import re
import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin

PDF_PATH = "catalogo-repuestos-y-accesorios.pdf"
IMAGE_DIR = "imagenes"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

os.makedirs(IMAGE_DIR, exist_ok=True)

# --------------------------------------------------
# 1. EXTRAER URLs DEL PDF
# --------------------------------------------------
def extract_urls_from_pdf(pdf_path):
    doc = pymupdf.open(pdf_path)
    urls = set()

    for page in doc:
        links = page.get_links()
        for link in links:
            if link.get("uri"):
                urls.add(link["uri"])

    return list(urls)



# --------------------------------------------------
# 2. SCRAPING + DESCARGA DE IMAGEN
# --------------------------------------------------
def process_product(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"❌ Error cargando {url}: {e}")
        return

    soup = BeautifulSoup(r.text, "html.parser")

    # ---- Extraer REFERENCIA (código) ----
    sku_div = soup.find("div", class_="product-sku")
    if not sku_div:
        print(f"⚠️ No se encontró product-sku en {url}")
        return

    sku_span = sku_div.find("span", itemprop="sku")
    if not sku_span or not sku_span.text.strip():
        print(f"⚠️ SKU vacío en {url}")
        return

    product_code = sku_span.text.strip()
    # Sanitizar caracteres inválidos para Windows (: * ? " < > | \ /)
    product_code = re.sub(r'[:\\*?"<>|/\\]', '_', product_code)

    if not product_code:
        print(f"⚠️ No se encontró referencia en {url}")
        return

    # ---- Buscar IMAGEN del producto (no el logo) ----
    # Usar selectores específicos para la imagen del producto
    img_tag = soup.select_one(".images-container img")
    if not img_tag:
        img_tag = soup.select_one(".product-cover img")
    if not img_tag:
        img_tag = soup.select_one(".product-image img")
    
    if not img_tag or not (img_tag.get("src") or img_tag.get("data-src")):
        print(f"⚠️ No se encontró imagen para {product_code}")
        return

    image_url = img_tag.get("src") or img_tag.get("data-src")
    image_url = urljoin(url, image_url)

    # ---- Descargar IMAGEN ----
    try:
        img_data = requests.get(image_url, headers=HEADERS, timeout=15).content
    except Exception as e:
        print(f"❌ Error descargando imagen {product_code}: {e}")
        return

    image_path = os.path.join(IMAGE_DIR, f"{product_code}.jpg")

    with open(image_path, "wb") as f:
        f.write(img_data)

    print(f"✅ Imagen guardada: {image_path}")


# --------------------------------------------------
# 3. PIPELINE
# --------------------------------------------------
def main():
    urls = extract_urls_from_pdf(PDF_PATH)
    print(f"🔗 URLs encontradas: {len(urls)}")

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] Procesando producto")
        process_product(url)


if __name__ == "__main__":
    print("Iniciando Scraping...")
    main()
