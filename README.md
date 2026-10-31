# AirDC++ Stream

[![Build](https://github.com/jmoruno/airdcpp-stream/actions/workflows/docker.yml/badge.svg?branch=main)](https://github.com/jmoruno/airdcpp-stream/actions/workflows/docker.yml) [![CodeQL](https://github.com/jmoruno/airdcpp-stream/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/jmoruno/airdcpp-stream/actions/workflows/codeql.yml) [![Trivy](https://github.com/jmoruno/airdcpp-stream/actions/workflows/trivy.yml/badge.svg?branch=main)](https://github.com/jmoruno/airdcpp-stream/actions/workflows/trivy.yml) [![Release](https://img.shields.io/github/v/release/jmoruno/airdcpp-stream)](https://github.com/jmoruno/airdcpp-stream/releases/latest) [![Docker pulls](https://img.shields.io/docker/pulls/jmorunofdz/airdcpp-stream)](https://hub.docker.com/r/jmorunofdz/airdcpp-stream) [![Image size](https://img.shields.io/docker/image-size/jmorunofdz/airdcpp-stream/stable)](https://hub.docker.com/r/jmorunofdz/airdcpp-stream) [![License](https://img.shields.io/github/license/jmoruno/airdcpp-stream)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/jmoruno)

**Español** · [English](README.en.md)

Addon de Stremio y Nuvio que busca en los hubs de AirDC++ (a través de
[airdcpp-torznab-bridge](https://github.com/jmoruno/airdcpp-torznab-bridge)) y reproduce mientras descarga.

- Resultados en castellano (o en todos los idiomas), con resolución, tamaño y número de fuentes.
- Resultados parciales con aviso de "🔄 Sigue buscando" mientras los hubs responden.
- Si Radarr o Sonarr ya tienen el fichero, aparece "📁 Biblioteca" y se reproduce desde el disco.
- Numeración absoluta para anime (Cinemeta) y búsqueda adelantada de los capítulos siguientes.

## Idioma

| Variable | Por defecto | Para qué |
| --- | --- | --- |
| `LANGUAGE` | `es` | Idioma de los textos en Stremio y Nuvio: `es` o `en` |
| `SPANISH_ONLY` | `true` con `es`, `false` con `en` | Mostrar solo resultados en castellano |

Para hubs en inglés, pon también `TMDB_LANGUAGE=en-US` en el bridge.

## Limitaciones

- MP4 o AVI con el índice al final no empiezan hasta que se descarga el fichero entero.
- No busca en eMule: lo que baje Mularr solo aparece cuando ya está en la biblioteca.

## Desplegar en Unraid (Portainer)

- Stack con `docker-compose.yml` (imagen `jmorunofdz/airdcpp-stream:stable`).
- Variables del stack: las de `.env.example`.
- Instalar en Stremio o Nuvio: `https://<PUBLIC_URL>/<TOKEN>/manifest.json`.

## Imagen y versiones

| Etiqueta | Canal | Para qué |
| --- | --- | --- |
| `stable` / `latest` | estable | Producción: última versión estable |
| `X.Y` / `X.Y.Z` (p. ej. `1.10.1`) | estable | Fijar una versión concreta o volver atrás |
| `beta` / `X.Y.Z-rc.N` | beta | Versiones candidatas, antes de pasar a estable |
| `dev` y otras ramas | desarrollo | Probar cambios sin tocar producción |
| `sha-<commit>` | — | Una build exacta |

Flujo de trabajo:

1. Los cambios se hacen en una rama. Cada push publica `:<rama>`.
2. Cuando funciona, se fusiona en `main`.
3. Para publicar una versión: **Actions → Imagen Docker → Run workflow** en `main`, con el número de versión.
   - **Estable** (`1.11.0`): release en GitHub y `:1.11.0`, `:1.11`, `:stable` y `:latest`.
   - **Beta** (`1.11.0-rc.1`): pre-release en GitHub y `:1.11.0-rc.1` y `:beta`.

## Licencia

[MIT](LICENSE): puedes usarlo, copiarlo, modificarlo y redistribuirlo libremente, también con fines comerciales, manteniendo el aviso de copyright.

## Aviso legal

Este software se ofrece **tal cual**, sin garantías de ningún tipo (ver [LICENSE](LICENSE)). El autor no se hace responsable de ningún daño, pérdida ni reclamación derivados de su uso.

- **No incluye, aloja ni distribuye contenido.** Es una herramienta técnica que solo se conecta a los servicios que configura cada usuario en su propia instalación.
- **Cada usuario es el único responsable** de cómo lo usa y de cumplir la legislación aplicable (incluida la de propiedad intelectual) y las normas de los servicios y hubs a los que se conecta. Úsalo solo con contenido que tengas derecho a descargar o reproducir.
- **No está afiliado** a AirDC++, Stremio, Nuvio, Radarr, Sonarr, TMDB, TVmaze ni a ningún otro proyecto o marca mencionado, ni cuenta con su respaldo. Los nombres pertenecen a sus respectivos titulares.

*This software is provided "as is", without warranty of any kind. It does not include, host or distribute any content. Users are solely responsible for how they use it and for complying with applicable laws and the terms of the services they connect to. Not affiliated with or endorsed by any of the projects mentioned.*

## Apoyar el proyecto

Si te resulta útil, puedes invitarme a un café: [buymeacoffee.com/jmoruno](https://buymeacoffee.com/jmoruno) ☕
