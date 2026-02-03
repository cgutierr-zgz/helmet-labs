"""
Browser Pool - Playwright wrapper para scraping con JS rendering.

Uso:
    from browser_pool import get_page_content, BrowserPool

    # Simple (abre y cierra browser cada vez):
    content = await get_page_content("https://example.com")

    # Con selector específico:
    html = await get_page_content("https://site.com", selector="div.main", wait=3)

    # Con pool (reutiliza browser):
    async with BrowserPool() as pool:
        content1 = await pool.get_content("https://site1.com")
        content2 = await pool.get_content("https://site2.com")
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, Playwright


class BrowserPool:
    """
    Pool de browsers para reutilizar instancias y evitar overhead de abrir/cerrar.
    
    Uso:
        async with BrowserPool(max_pages=5) as pool:
            content = await pool.get_content(url)
    """
    
    def __init__(self, max_pages: int = 5, headless: bool = True):
        self.max_pages = max_pages
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        self._semaphore = asyncio.Semaphore(self.max_pages)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def get_content(
        self,
        url: str,
        selector: Optional[str] = None,
        wait: float = 2.0,
        timeout: float = 30.0,
        wait_until: str = 'domcontentloaded'
    ) -> str:
        """
        Navega a URL y extrae contenido.
        
        Args:
            url: URL a visitar
            selector: CSS selector para extraer (None = toda la página)
            wait: Segundos adicionales de espera tras carga inicial
            timeout: Timeout máximo en segundos
            wait_until: Evento de espera ('domcontentloaded', 'load', 'networkidle')
            
        Returns:
            HTML content (outer_html del selector o page.content())
        """
        if not self._browser:
            raise RuntimeError("BrowserPool not initialized. Use 'async with BrowserPool() as pool:'")
        
        async with self._semaphore:
            context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            try:
                await page.goto(url, timeout=timeout * 1000, wait_until=wait_until)
                
                # Espera adicional para que JS renderice
                if wait > 0:
                    await asyncio.sleep(wait)
                
                if selector:
                    element = await page.query_selector(selector)
                    if element:
                        return await element.inner_html()
                    return ""
                
                return await page.content()
            
            except Exception as e:
                raise RuntimeError(f"Error fetching {url}: {e}") from e
            
            finally:
                await context.close()


async def get_page_content(
    url: str,
    selector: Optional[str] = None,
    wait: float = 2.0,
    timeout: float = 30.0,
    headless: bool = True,
    wait_until: str = 'domcontentloaded'
) -> str:
    """
    Función standalone para obtener contenido de una página.
    Abre browser, navega, extrae, cierra.
    
    Para múltiples URLs, usar BrowserPool es más eficiente.
    
    Args:
        url: URL a visitar
        selector: CSS selector para extraer (None = toda la página)
        wait: Segundos adicionales de espera tras carga
        timeout: Timeout máximo en segundos
        headless: Ejecutar sin ventana visible
        wait_until: Evento de espera ('domcontentloaded', 'load', 'networkidle')
        
    Returns:
        HTML content
    """
    async with BrowserPool(max_pages=1, headless=headless) as pool:
        return await pool.get_content(url, selector, wait, timeout, wait_until)


# === Test rápido ===
async def _test_polymarket():
    """Test: scrape Polymarket y extraer títulos de mercados."""
    print("🎭 Testing Playwright con Polymarket...")
    
    async with BrowserPool() as pool:
        content = await pool.get_content(
            "https://polymarket.com",
            wait=5,  # Polymarket carga mucho JS, necesita más tiempo
            timeout=60
        )
    
    # Buscar títulos de mercados en el HTML
    from html.parser import HTMLParser
    
    class MarketTitleParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.titles = []
            self.in_title = False
            self.current_class = ""
            
        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            # Polymarket usa clases específicas para títulos
            if tag == 'p' and 'class' in attrs_dict:
                classes = attrs_dict['class']
                # Los títulos suelen estar en elementos con ciertos patrones
                if 'c-dhzjXW' in classes or 'font-medium' in classes.lower():
                    self.in_title = True
                    
        def handle_endtag(self, tag):
            if tag == 'p':
                self.in_title = False
                
        def handle_data(self, data):
            data = data.strip()
            if data and len(data) > 10 and len(data) < 200:
                # Filtrar títulos que parecen mercados (heurística simple)
                if '?' in data or any(word in data.lower() for word in ['will', 'price', 'win', 'election', 'trump', 'bitcoin']):
                    if data not in self.titles:
                        self.titles.append(data)
    
    parser = MarketTitleParser()
    parser.feed(content)
    
    # También buscar con regex como backup
    import re
    # Buscar textos que parecen preguntas de mercado
    questions = re.findall(r'>([^<]{15,150}\?)<', content)
    
    all_titles = list(set(parser.titles + questions))[:20]
    
    print(f"\n✅ Página cargada ({len(content):,} bytes)")
    print(f"📊 Encontrados {len(all_titles)} posibles títulos de mercados:\n")
    
    for i, title in enumerate(all_titles[:10], 1):
        print(f"  {i}. {title}")
    
    if len(all_titles) > 10:
        print(f"  ... y {len(all_titles) - 10} más")
    
    return len(content) > 10000  # Success si tenemos contenido sustancial


if __name__ == "__main__":
    success = asyncio.run(_test_polymarket())
    print(f"\n{'✅ TEST PASSED' if success else '❌ TEST FAILED'}")
