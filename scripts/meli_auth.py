"""Helper de OAuth para la API de Mercado Libre (flujo Authorization Code, sin PKCE).

Uso:
    python scripts/meli_auth.py

Que hace:
  1. Lee meli_client_id / meli_client_secret / meli_redirect_uri de config.yaml.
  2. Te imprime el link de autorizacion. Lo abris en el navegador (logueado en ML),
     autorizas, y ML te redirige a tu redirect_uri con `?code=...` en la URL.
     Con redirect a https://httpbin.org/get vas a VER el code en pantalla (JSON).
  3. Pegas ese code (o la URL completa) y el script lo canjea por access_token +
     refresh_token, y los guarda en meli_token.json (gitignoreado).
  4. Hace una prueba: consulta el search de inmuebles (categoria MLA1459) para
     confirmar si la API oficial realmente devuelve listados con tu token.

No requiere levantar ningun servidor: el code se copia a mano del navegador.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
import yaml

# Endpoints de Argentina
AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
SEARCH_URL = "https://api.mercadolibre.com/sites/MLA/search"
REALESTATE_CATEGORY = "MLA1459"  # Inmuebles

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
TOKEN_PATH = ROOT / "meli_token.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"No encontre {CONFIG_PATH}. Copia config.example.yaml a config.yaml.")
    with CONFIG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    faltan = [k for k in ("meli_client_id", "meli_client_secret", "meli_redirect_uri")
              if not cfg.get(k)]
    if faltan:
        sys.exit(
            "Faltan en config.yaml: " + ", ".join(faltan) + "\n"
            "Agregalos asi:\n"
            '  meli_client_id: "TU_APP_ID"\n'
            '  meli_client_secret: "TU_CLIENT_SECRET"\n'
            '  meli_redirect_uri: "https://httpbin.org/get"\n'
        )
    return cfg


def _extract_code(pegado: str) -> str:
    """Acepta el code pelado o la URL completa del redirect y devuelve el code."""
    pegado = pegado.strip()
    if pegado.startswith("http"):
        qs = parse_qs(urlparse(pegado).query)
        code = qs.get("code", [""])[0]
        if not code:
            sys.exit("No encontre `code` en esa URL. Fijate que tenga ?code=...")
        return code
    return pegado


def _exchange_code_for_tokens(cfg: dict, code: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "client_id": cfg["meli_client_id"],
            "client_secret": cfg["meli_client_secret"],
            "code": code,
            "redirect_uri": cfg["meli_redirect_uri"],
        },
        timeout=30,
    )
    if not resp.ok:
        sys.exit(f"Fallo el canje de token ({resp.status_code}):\n{resp.text}")
    return resp.json()


def _probe_search(access_token: str) -> None:
    print("\n--- Prueba: search de inmuebles (MLA1459) con tu token ---")
    params = {"category": REALESTATE_CATEGORY, "limit": 5}
    resp = requests.get(
        SEARCH_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        timeout=30,
    )
    print(f"GET {SEARCH_URL}?{urlencode(params)} -> {resp.status_code}")
    if not resp.ok:
        print("La API NO devolvio resultados con tu token. Respuesta:")
        print(resp.text[:600])
        print("\n=> El search oficial parece restringido. Avisame el status y el texto.")
        return
    data = resp.json()
    results = data.get("results", [])
    print(f"OK! total reportado: {data.get('paging', {}).get('total')} | en esta pagina: {len(results)}")
    for it in results[:3]:
        print(f"  - {it.get('id')} | {str(it.get('title'))[:60]} | "
              f"{it.get('price')} {it.get('currency_id')}")
    print("\n=> Si ves inmuebles aca, la API oficial sirve y construyo el gateway.")


def main() -> int:
    cfg = _load_config()

    auth_link = f"{AUTH_URL}?" + urlencode({
        "response_type": "code",
        "client_id": cfg["meli_client_id"],
        "redirect_uri": cfg["meli_redirect_uri"],
    })
    print("1) Abri este link en el navegador (logueado en tu cuenta de ML) y autoriza:\n")
    print(f"   {auth_link}\n")
    print("2) ML te va a redirigir a tu redirect_uri. Copia el `code` (o pega la URL")
    print("   completa que quedo en la barra de direcciones / el JSON de httpbin).\n")

    pegado = input("Pega aca el code o la URL del redirect: ").strip()
    code = _extract_code(pegado)

    tokens = _exchange_code_for_tokens(cfg, code)
    TOKEN_PATH.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    print(f"\nTokens guardados en {TOKEN_PATH.name}")
    print(f"  access_token vence en {tokens.get('expires_in')} s "
          f"({round(tokens.get('expires_in', 0) / 3600, 1)} h)")
    print(f"  refresh_token presente: {'si' if tokens.get('refresh_token') else 'NO'}")
    print(f"  user_id: {tokens.get('user_id')}")

    _probe_search(tokens["access_token"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
