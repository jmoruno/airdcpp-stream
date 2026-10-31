# airdcpp-stream

Addon de Stremio y Nuvio que busca en los hubs de AirDC++ (a través de
[airdcpp-torznab-bridge](https://github.com/jmoruno/airdcpp-torznab-bridge)) y reproduce mientras descarga.

- Resultados en castellano, con resolución, tamaño y número de fuentes.
- Resultados parciales con aviso de "🔄 Sigue buscando" mientras los hubs responden.
- Si Radarr o Sonarr ya tienen el fichero, aparece "📁 Biblioteca" y se reproduce desde el disco.
- Numeración absoluta para anime (Cinemeta) y búsqueda adelantada de los capítulos siguientes.

## Limitaciones

- MP4 o AVI con el índice al final no empiezan hasta que se descarga el fichero entero.
- No busca en eMule: lo que baje Mularr solo aparece cuando ya está en la biblioteca.

## Desplegar en Unraid (Portainer)

- Stack con `docker-compose.unraid.yml` (imagen `jmorunofdz/airdcpp-stream:latest`, la publica GitHub Actions en cada push a `main`).
- Variables del stack: las de `.env.example`.
- Instalar en Stremio o Nuvio: `https://<PUBLIC_URL>/<TOKEN>/manifest.json`.
