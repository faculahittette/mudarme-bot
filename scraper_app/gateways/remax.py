from .base import BaseGateway


class RemaxGateway(BaseGateway):
    # La API de Remax pagina con page=0 como primera pagina (0-indexed).
    first_page = 0

    def __init__(self):
        self._name = 'Remax'
