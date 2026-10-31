# AirDC++ Stream

[![Build](https://github.com/jmoruno/airdcpp-stream/actions/workflows/docker.yml/badge.svg?branch=main)](https://github.com/jmoruno/airdcpp-stream/actions/workflows/docker.yml) [![CodeQL](https://github.com/jmoruno/airdcpp-stream/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/jmoruno/airdcpp-stream/actions/workflows/codeql.yml) [![Trivy](https://github.com/jmoruno/airdcpp-stream/actions/workflows/trivy.yml/badge.svg?branch=main)](https://github.com/jmoruno/airdcpp-stream/actions/workflows/trivy.yml) [![Release](https://img.shields.io/github/v/release/jmoruno/airdcpp-stream)](https://github.com/jmoruno/airdcpp-stream/releases/latest) [![Docker pulls](https://img.shields.io/docker/pulls/jmorunofdz/airdcpp-stream)](https://hub.docker.com/r/jmorunofdz/airdcpp-stream) [![Image size](https://img.shields.io/docker/image-size/jmorunofdz/airdcpp-stream/stable)](https://hub.docker.com/r/jmorunofdz/airdcpp-stream) [![License](https://img.shields.io/github/license/jmoruno/airdcpp-stream)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/jmoruno)

[Español](README.md) · **English**

Stremio and Nuvio addon that searches your AirDC++ hubs (through
[airdcpp-torznab-bridge](https://github.com/jmoruno/airdcpp-torznab-bridge)) and plays while downloading.

- Results with resolution, size and number of sources.
- Partial results with a "🔄 Still searching" notice while hubs keep answering.
- If Radarr or Sonarr already have the file, "📁 Library" appears and plays straight from disk.
- Absolute numbering for anime (Cinemeta) and early search for the next episodes.

## Language

| Variable | Default | Use |
| --- | --- | --- |
| `LANGUAGE` | `es` | Language of the texts in Stremio and Nuvio: `es` or `en` |
| `SPANISH_ONLY` | `true` with `es`, `false` with `en` | Show only Spanish results |

For English hubs, also set `TMDB_LANGUAGE=en-US` in the bridge.

## Limitations

- MP4 or AVI files with the index at the end do not start until fully downloaded.
- It does not search eMule: what Mularr downloads only shows up once it is in the library.

## Deploying on Unraid (Portainer)

- Stack from `docker-compose.yml` (image `jmorunofdz/airdcpp-stream:stable`).
- Stack variables: those in `.env.example`.
- Install in Stremio or Nuvio: `https://<PUBLIC_URL>/<TOKEN>/manifest.json`.

## Image and versions

| Tag | Channel | Use |
| --- | --- | --- |
| `stable` / `latest` | stable | Production: latest stable release |
| `X.Y` / `X.Y.Z` (e.g. `1.10.1`) | stable | Pin a specific version or roll back |
| `beta` / `X.Y.Z-rc.N` | beta | Release candidates, before going stable |
| `dev` and other branches | development | Test changes without touching production |
| `sha-<commit>` | — | One exact build |

Workflow:

1. Changes are made on a branch. Each push publishes `:<branch>`.
2. Once it works, it is merged into `main`.
3. To publish a release: **Actions → Imagen Docker → Run workflow** on `main`, with the version number.
   - **Stable** (`1.11.0`): GitHub release and `:1.11.0`, `:1.11`, `:stable` and `:latest`.
   - **Beta** (`1.11.0-rc.1`): GitHub pre-release and `:1.11.0-rc.1` and `:beta`.

## License

[MIT](LICENSE): you may use, copy, modify and redistribute it freely, including for commercial purposes, as long as the copyright notice is kept.

## Disclaimer

This software is provided **as is**, without warranty of any kind (see [LICENSE](LICENSE)). The author is not liable for any damage, loss or claim arising from its use.

- **It does not include, host or distribute any content.** It is a technical tool that only connects to the services each user configures in their own installation.
- **Each user is solely responsible** for how they use it and for complying with applicable law (including copyright) and the rules of the services and hubs they connect to. Use it only with content you have the right to download or play.
- **Not affiliated** with or endorsed by AirDC++, Stremio, Nuvio, Radarr, Sonarr, TMDB, TVmaze or any other project or brand mentioned. Names belong to their respective owners.

## Support

If you find it useful, you can buy me a coffee: [buymeacoffee.com/jmoruno](https://buymeacoffee.com/jmoruno) ☕
