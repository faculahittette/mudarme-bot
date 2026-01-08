from typing import Set

from bs4 import BeautifulSoup

from .base import BaseParser
from posting_app.database import Posting, PostingRepository


class MercadolibreParser(BaseParser):
    name = "Mercado Libre"
    url_base = "https://inmuebles.mercadolibre.com.ar"

    base_info_class = "andes-card"
    base_info_tag = "div"
    link_regex = "a.poly-component__title"
    title_regex = "a.poly-component__title"
    price_regex = "span.andes-money-amount__fraction"
    description_regex = "ul.poly-attributes_list"
    location_regex = "span.poly-component__location"

    def extract_data(self) -> Set[Posting]:
        """Extracting data and returning list of objects"""
        postings = set()
        base_info_soaps = self.soup.find_all(
            self.base_info_tag, class_=self.base_info_class
        )

        for base_info_soap in base_info_soaps:
            link_container = base_info_soap.select_one(self.link_regex)
            title_container = base_info_soap.select_one(self.title_regex)
            price_container = base_info_soap.select_one(self.price_regex)
            description_container = base_info_soap.select_one(self.description_regex)
            location_container = base_info_soap.select_one(self.location_regex)

            if not (
                link_container
                and title_container
                and price_container
                and description_container
                and location_container
            ):
                continue

            href = link_container.get("href", "").split('#')[0]
            sha = self.get_id(href.split("#")[0])
            price = self.sanitize_text(price_container.text)
            title = self.sanitize_text(title_container.text)
            description = self.sanitize_text(description_container.text)
            location = self.sanitize_text(location_container.text)

            posting_repository = PostingRepository()
            if posting_repository.get_posting_by_sha(sha):
                continue

            new_posting = Posting(
                sha=sha,
                url=href,
                title=title,
                price="$ %s" % price,
                description=description,
                location=location,
            )
            postings.add(new_posting)

        return postings