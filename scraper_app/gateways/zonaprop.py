from .base import CLOUDSCRAPER, PLAIN, BaseGateway


class ZonapropGateway(BaseGateway):
    # Desde servidores en la nube (GitHub Actions) Cloudflare le da 403 a
    # cloudscraper pero deja pasar un request comun con headers de navegador.
    # En casa funcionan los dos: probamos primero el simple y caemos al otro.
    clients = [PLAIN, CLOUDSCRAPER]
    publication_in_detail_page = True

    def __init__(self):
        self._name = 'Zonaprop'
