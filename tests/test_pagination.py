from scraper_app.gateways import MercadolibreGateway
from scraper_app.services import ScraperService


class _FakeGateway:
    paginated = True

    def __init__(self, first_page):
        self.first_page = first_page
        self.requested = []

    def make_request(self, url):
        self.requested.append(url)
        return ''


class _FakeMercadolibreGateway(MercadolibreGateway):
    '''Hereda la logica real de page_param/paginated, pero no toca la red.'''

    def __init__(self):
        super().__init__()
        self.requested = []

    def make_request(self, url):
        self.requested.append(url)
        return ''


class _FakeParser:
    def get_soup_object(self, html):
        pass

    def extract_data(self):
        return set()


def test_first_page_zero_indexed():
    gw = _FakeGateway(first_page=0)
    svc = ScraperService(pages=3, url='http://x?page={}', gateway=gw, parser=_FakeParser())
    svc.get_postings_from_scraper()
    assert gw.requested == ['http://x?page=0', 'http://x?page=1', 'http://x?page=2']


def test_first_page_one_indexed_default():
    gw = _FakeGateway(first_page=1)
    svc = ScraperService(pages=2, url='http://x?page={}', gateway=gw, parser=_FakeParser())
    svc.get_postings_from_scraper()
    assert gw.requested == ['http://x?page=1', 'http://x?page=2']


def test_mercadolibre_page_param_maps_to_desde_offset():
    gw = MercadolibreGateway()
    # pagina 1 -> 1, pagina 2 -> 49, pagina 3 -> 97 (48 por pagina)
    assert [gw.page_param(p) for p in (1, 2, 3)] == [1, 49, 97]


def test_mercadolibre_paginates_with_desde_urls():
    gw = _FakeMercadolibreGateway()
    url = 'https://inmuebles.mercadolibre.com.ar/departamentos/venta/_Desde_{}_NoIndex_True'
    svc = ScraperService(pages=3, url=url, gateway=gw, parser=_FakeParser())
    svc.get_postings_from_scraper()
    assert gw.requested == [
        'https://inmuebles.mercadolibre.com.ar/departamentos/venta/_Desde_1_NoIndex_True',
        'https://inmuebles.mercadolibre.com.ar/departamentos/venta/_Desde_49_NoIndex_True',
        'https://inmuebles.mercadolibre.com.ar/departamentos/venta/_Desde_97_NoIndex_True',
    ]
