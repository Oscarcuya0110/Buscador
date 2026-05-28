# Normativa Telecom · OSIPTEL

Buscador ligero de normativas del sector telecomunicaciones. Lee un archivo JSON estático y redirige al documento oficial en OSIPTEL o el Diario Oficial. No requiere base de datos ni backend.

## Estructura del proyecto

```
osiptel-buscador/
├── index.html                  ← Plataforma completa (un solo archivo)
├── indice_normas_telecom.json  ← Índice generado por el scraper
├── scraper_osiptel.py          ← Script para regenerar el índice
└── README.md
```

## Despliegue en GitHub Pages

1. Crear un repositorio en GitHub (puede ser público o privado con Pages habilitado).
2. Subir los archivos `index.html` e `indice_normas_telecom.json` a la rama `main`.
3. En el repositorio: **Settings → Pages → Source → Deploy from branch → main / root**.
4. En ~1 minuto la plataforma estará disponible en:
   ```
   https://<tu-usuario>.github.io/<nombre-del-repo>/
   ```

## Actualizar el índice

Ejecuta el scraper periódicamente (se recomienda mensual):

```bash
pip install requests beautifulsoup4
python scraper_osiptel.py
```

Luego sube el nuevo `indice_normas_telecom.json` al repositorio. GitHub Pages lo sirve automáticamente.

### Automatización con GitHub Actions (opcional)

Puedes programar el scraper como Action para que corra cada mes sin intervención manual. Crea `.github/workflows/actualizar_indice.yml` con:

```yaml
name: Actualizar índice de normas

on:
  schedule:
    - cron: '0 6 1 * *'   # primer día de cada mes a las 6am UTC
  workflow_dispatch:       # también permite ejecución manual

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install requests beautifulsoup4
      - run: python scraper_osiptel.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "Actualizar índice de normas OSIPTEL"
          file_pattern: indice_normas_telecom.json
```

## Estructura del JSON

Cada objeto en `indice_normas_telecom.json` tiene estos campos:

| Campo         | Tipo     | Descripción                                      |
|---------------|----------|--------------------------------------------------|
| `titulo`      | string   | Nombre completo de la norma                      |
| `tipo`        | string   | Resolución CD / Decreto Supremo / etc.           |
| `fecha`       | string   | Fecha en formato `YYYY-MM-DD`                    |
| `tags`        | string[] | Palabras clave del sector que coinciden          |
| `url_oficial` | string   | Enlace al documento en OSIPTEL o Diario Oficial  |

## Agregar más sectores

Para cubrir otros reguladores (OSINERGMIN, SUNASS, OSITRAN), duplica la lógica del scraper con nuevas `PALABRAS_CLAVE` y `URLS_OBJETIVO`, y genera archivos JSON separados por sector. El `index.html` puede adaptarse para cargar múltiples índices.
