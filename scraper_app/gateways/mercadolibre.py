from .base import CLOUDSCRAPER, PLAIN, BaseGateway


class MercadolibreGateway(BaseGateway):
    # ML pagina por offset de item en el path (`_Desde_49`, `_Desde_97`, ...),
    # con 48 resultados por pagina. `_Desde_1` equivale a la primera pagina,
    # asi que un unico template `_Desde_{}` sirve para todas.
    _PER_PAGE = 48
    # Desde una compu de casa responden los dos; el request comun es mas liviano.
    clients = [PLAIN, CLOUDSCRAPER]
    publication_in_detail_page = True

    def __init__(self):
        self._name = 'Mercadolibre'

    def page_param(self, page: int) -> int:
        # page 1 -> 1 (_Desde_1), page 2 -> 49, page 3 -> 97, ...
        return (page - 1) * self._PER_PAGE + 1
