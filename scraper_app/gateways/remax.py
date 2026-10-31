from .base import BaseGateway


class RemaxGateway(BaseGateway):
    # La API de Remax pagina con page=0 como primera pagina (0-indexed).
    first_page = 0
    # Coincide con `pageSize=24` de la URL en searches.yaml.
    page_size = 24

    def __init__(self):
        self._name = 'Remax'
