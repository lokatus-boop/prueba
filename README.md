 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/README.md b/README.md
index bd5ce160662275438a6cfec69c0c44423f794bd4..87cdb20b485d81809719f168db5bd7cd39078e3e 100644
--- a/README.md
+++ b/README.md
@@ -1 +1,48 @@
-# prueba
\ No newline at end of file
+# Scraper de Premier Padel 2025
+
+Esta utilidad permite descargar la información pública disponible en [padelfip.com](https://www.padelfip.com/es/) sobre:
+
+- Torneos **Premier Padel** del año indicado (por defecto 2025).
+- Resultados y estadísticas de cada partido disponibles en la página de cada torneo.
+- Ranking oficial y clasificación Race (masculino y femenino).
+
+Los datos se indexan por jugador para poder consultar de forma interactiva los partidos disputados, sus compañeros de pareja y su posición en el ranking y en la race.
+
+## Requisitos
+
+```bash
+python3 -m venv .venv
+source .venv/bin/activate
+pip install -r requirements.txt
+```
+
+> **Nota:** La ejecución necesita acceso a Internet para consultar la web oficial de la FIP.
+
+## Uso
+
+1. Ejecuta el script principal (puedes activar los logs para ver el progreso del scraping):
+
+   ```bash
+   python main.py --year 2025 --log INFO
+   ```
+
+   Verás en pantalla el listado de torneos Premier Padel 2025 encontrados y, mientras se descarga la información, mensajes como `Descargando torneos Premier Padel del 2025`.
+
+2. Cuando termine la descarga se abrirá un prompt interactivo:
+
+   - Introduce parte del nombre del jugador para ver sus datos (ejemplo: `coello`).
+   - Escribe `lista` para obtener un listado de todos los jugadores localizados.
+   - Escribe `salir` para terminar el programa.
+
+3. Al seleccionar un jugador se mostrarán los partidos disputados con fecha, ronda, pareja, rivales, marcador y estadísticas agregadas, además de su posición en el ranking y la race.
+
+## Estructura del proyecto
+
+- `fip_padel/client.py`: lógica de scraping y normalización de datos.
+- `fip_padel/models.py`: modelos de datos utilizados por la aplicación.
+- `fip_padel/player_index.py`: herramientas para agrupar partidos y rankings por jugador.
+- `main.py`: interfaz de línea de comandos.
+
+## Aviso legal
+
+Esta herramienta está pensada para uso personal y educativo. Respeta los términos de uso del sitio web de la FIP y evita realizar peticiones excesivas.
 
EOF
)
