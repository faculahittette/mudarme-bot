from .base import BaseGateway, CLOUDSCRAPER, PLAIN


class Century21Gateway(BaseGateway):
    '''Century 21 Argentina: `/search?...&page=N` (paginas desde 1, 16 avisos).'''

    clients = [PLAIN, CLOUDSCRAPER]

    def __init__(self):
        self._name = 'Century 21'
