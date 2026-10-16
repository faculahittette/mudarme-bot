from .base import BaseGateway


class BnaGateway(BaseGateway):
    '''API JSON de BNA +Hogares (mashogaresconbna.com.ar/api/propiedades).

    Pagina con `page=1, 2, ...`. Todo lo publicado ahi es apto credito BNA.
    '''

    def __init__(self):
        self._name = 'BNA +Hogares'
