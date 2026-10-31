from .base import BaseGateway


class BnaGateway(BaseGateway):
    '''API JSON de BNA +Hogares (mashogaresconbna.com.ar/api/propiedades).

    Pagina con `page=1, 2, ...`. Todo lo publicado ahi es apto credito BNA.
    '''

    # La API a veces tarda mas de 30s en responder.
    timeout_seconds = 60
    # Coincide con `limit=48` de la URL en searches.yaml.
    page_size = 48

    def __init__(self):
        self._name = 'BNA +Hogares'
