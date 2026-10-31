# Registro de cambios

Versiones con [SemVer](https://semver.org/lang/es/). Las notas de cada versión también están en las [releases](../../releases).

## [1.11.0] - 2026-10-31

### Añadido

- `LANGUAGE=es|en`: textos en castellano o en inglés en Stremio y Nuvio. `SPANISH_ONLY` sigue a `LANGUAGE` si no se indica.
- README en inglés.
- Análisis de seguridad con CodeQL y Trivy en cada push y cada semana.

### Seguridad

- Inicia sesión en el bridge con usuario y contraseña en vez de calcular la cookie a partir de la contraseña.
- Las rutas de fichero que llegan en la URL se validan: no pueden salir de la carpeta de descargas ni de la biblioteca.
- La imagen ya no incluye `pip`, que no se usa y tenía vulnerabilidades conocidas.

## [1.10.1] - 2026-10-31

- Licencia MIT, aviso legal y documentación de despliegue.

## [1.10.0] - 2026-10-31

- Versión inicial publicada: búsqueda en hubs de AirDC++, resultados parciales, biblioteca de Radarr/Sonarr y numeración absoluta para anime.
