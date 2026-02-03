#!/usr/bin/env python3
"""
Test de integración: simula servidor HTTP que devuelve 429 y verifica
que monitor_daemon.py maneja correctamente el rate limiting.

Levanta un servidor HTTP local que:
- Devuelve 429 en las primeras 2 requests
- Devuelve 200 OK después

Verifica que monitor_daemon:
- Detecta el 429
- Aumenta el backoff
- Eventualmente recupera

Uso:
    python test_rate_limiter_integration.py
"""

import asyncio
import json
import time
from pathlib import Path
from aiohttp import web
from monitor_daemon import MonitorDaemon

# Colores
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log(color, msg):
    print(f"{color}{msg}{RESET}")


# Contador global de requests
REQUEST_COUNT = 0


async def test_handler(request):
    """Handler que devuelve 429 las primeras 2 veces, luego RSS válido."""
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    
    log(YELLOW, f"📨 Request #{REQUEST_COUNT} recibida")
    
    if REQUEST_COUNT <= 2:
        log(RED, f"   → Devolviendo 429 (Too Many Requests)")
        return web.Response(status=429, text="Too Many Requests")
    
    # RSS válido después del 3er intento
    log(GREEN, f"   → Devolviendo 200 OK con RSS")
    rss = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>http://localhost:8765/test</link>
    <description>Test</description>
    <item>
      <title>Test Item 1</title>
      <link>http://localhost:8765/item1</link>
      <description>First test item</description>
      <guid>test-item-1</guid>
      <pubDate>Mon, 03 Feb 2025 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""
    return web.Response(text=rss, content_type='application/rss+xml')


async def start_test_server():
    """Levanta servidor HTTP de prueba en puerto 8765."""
    app = web.Application()
    app.router.add_get('/test', test_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, 'localhost', 8765)
    await site.start()
    
    log(GREEN, "🚀 Servidor de prueba iniciado en http://localhost:8765")
    return runner


async def test_integration():
    """Test de integración completo."""
    global REQUEST_COUNT
    REQUEST_COUNT = 0
    
    log(BLUE, "\n" + "="*60)
    log(BLUE, "🧪 Rate Limiter Integration Test")
    log(BLUE, "="*60 + "\n")
    
    # Crear archivos temporales
    test_dir = Path(__file__).parent.parent / "data" / "test_rate_limiter"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    sources_file = test_dir / "sources.json"
    state_file = test_dir / "monitor_state.json"
    events_file = test_dir / "scraped_events.json"
    
    # Configuración de test
    sources_config = {
        "sources": [
            {
                "id": "test-429",
                "url": "http://localhost:8765/test",
                "type": "rss",
                "interval_seconds": 10,
                "category": "test",
                "priority": 5
            }
        ],
        "config": {
            "max_concurrent_requests": 1,
            "rate_limit_per_domain_ms": 500,  # 0.5s entre requests
            "max_retries": 3,
            "retry_base_delay_ms": 1000,  # 1s base delay
            "max_consecutive_errors": 10,
            "request_timeout_ms": 5000,
            "user_agent_rotation": True
        }
    }
    
    sources_file.write_text(json.dumps(sources_config, indent=2))
    log(GREEN, f"✓ Configuración creada en {sources_file}")
    
    # Limpiar estado previo
    for f in [state_file, events_file]:
        if f.exists():
            f.unlink()
    
    # Iniciar servidor
    runner = await start_test_server()
    
    try:
        # Esperar un momento para que el servidor esté listo
        await asyncio.sleep(0.5)
        
        # Crear daemon y ejecutar un ciclo
        daemon = MonitorDaemon(sources_file=sources_file, verbose=True)
        
        # Modificar paths del daemon para usar directorio de test
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        import monitor_daemon as md
        md.STATE_FILE = state_file
        md.EVENTS_FILE = events_file
        
        log(BLUE, "\n--- Ejecutando ciclo de monitoring ---\n")
        start = time.time()
        events = await daemon.run_cycle()
        elapsed = time.time() - start
        
        log(BLUE, f"\n--- Ciclo completado en {elapsed:.2f}s ---\n")
        
        # Verificaciones
        log(BLUE, "\n📊 Verificando resultados...\n")
        
        # 1. Debería haber hecho exactamente 3 requests (2 fallos + 1 éxito)
        assert REQUEST_COUNT == 3, f"Esperaba 3 requests, pero se hicieron {REQUEST_COUNT}"
        log(GREEN, f"✓ Número de requests correcto: {REQUEST_COUNT}")
        
        # 2. Debería haber generado 1 evento (primer run graba estado, no genera eventos)
        # En este caso como es el primer run, no debería generar eventos
        log(YELLOW, f"  Eventos generados: {len(events)} (primer run no genera eventos)")
        
        # 3. Verificar que el estado se guardó
        assert state_file.exists(), "Estado no se guardó"
        state = json.loads(state_file.read_text())
        assert "test-429" in state, "Estado no contiene la fuente"
        log(GREEN, f"✓ Estado guardado correctamente")
        
        # 4. Verificar que hay items en el estado
        source_state = state["test-429"]
        assert source_state.get("items_count", 0) > 0, "No se parsearon items"
        log(GREEN, f"✓ Items parseados: {source_state['items_count']}")
        
        # 5. Verificar que se registró el éxito (consecutive_errors = 0)
        assert source_state.get("consecutive_errors", 1) == 0, "Errores consecutivos no se resetearon"
        log(GREEN, f"✓ Errores consecutivos reseteados tras éxito")
        
        # 6. Verificar que el tiempo total indica backoff (debería ser > 2s por los retries)
        assert elapsed >= 2.0, f"Tiempo demasiado corto ({elapsed:.2f}s), esperaba >2s por retries"
        log(GREEN, f"✓ Tiempo total indica backoff: {elapsed:.2f}s")
        
        log(GREEN, "\n✅ ALL CHECKS PASSED\n")
        
        # Limpiar archivos de test
        for f in [sources_file, state_file, events_file]:
            if f.exists():
                f.unlink()
        
        # Intentar borrar directorio si está vacío
        try:
            test_dir.rmdir()
        except OSError:
            pass  # No pasa nada si no está vacío
        
    finally:
        # Cerrar servidor
        await runner.cleanup()
        log(YELLOW, "🛑 Servidor de prueba cerrado")
    
    log(BLUE, "\n" + "="*60)
    log(GREEN, "✅ INTEGRATION TEST PASSED")
    log(BLUE, "="*60 + "\n")
    
    return True


async def main():
    try:
        success = await test_integration()
        return success
    except AssertionError as e:
        log(RED, f"\n❌ TEST FAILED: {e}\n")
        return False
    except Exception as e:
        log(RED, f"\n💥 TEST ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = asyncio.run(main())
    exit(0 if success else 1)
