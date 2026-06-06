from scraper_app.services import ScraperService


class _FakeGateway:
    paginated = True

    def __init__(self, first_page):
        self.first_page = first_page
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
