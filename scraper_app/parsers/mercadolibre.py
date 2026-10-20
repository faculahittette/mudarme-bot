from typing import Set

from .base import BaseParser
from posting_app.database import Posting


class MercadolibreParser(BaseParser):
    name = "Mercado Libre"
    url_base = "https://inmuebles.mercadolibre.com.ar"

    # Solo los resultados de la busqueda: la pagina tambien trae avisos
    # "recomendados" con la misma tarjeta que no cumplen los filtros.
    item_selector = "ol.ui-search-layout li.ui-search-layout__item"
    link_regex = "a.poly-component__title"
    currency_regex = "span.andes-money-amount__currency-symbol"
    price_regex = "span.andes-money-amount__fraction"
    description_regex = "ul.poly-attributes_list"
    location_regex = "span.poly-component__location"

    def extract_data(self) -> Set[Posting]:
        """Extracting data and returning list of objects"""
        postings = set()
        self.page_keys = set()

        for item in self.soup.select(self.item_selector):
            link_container = item.select_one(self.link_regex)
            if not link_container:
                continue

            # Sin `#polycard...`: son parametros de tracking que cambian siempre.
            href = link_container.get("href", "").split("#")[0].split("?")[0]
            if not href:
                continue
            self.page_keys.add(href)

            sha = self.get_id(href)
            postings.add(Posting(
                sha=sha,
                url=href,
                title=self.sanitize_text(link_container.get_text())[:100],
                price=self._price(item),
                description=self._text(item, self.description_regex),
                location=self._text(item, self.location_regex),
            ))

        return postings

    def _price(self, item) -> str:
        amount = self._text(item, self.price_regex)
        if not amount:
            return 'Consultar precio'
        currency = self._text(item, self.currency_regex) or '$'
        return f'{currency} {amount}'

    def _text(self, item, selector: str) -> str:
        node = item.select_one(selector)
        if not node:
            return ''
        # Los atributos (ambientes, m2, dormitorios) vienen como <li> separados.
        parts = [self.sanitize_text(li.get_text()) for li in node.select('li')]
        return ' | '.join(p for p in parts if p) if parts else self.sanitize_text(node.get_text())
