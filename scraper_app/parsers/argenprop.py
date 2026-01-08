from typing import Set

from bs4 import BeautifulSoup

from .base import BaseParser
from posting_app.database import Posting, PostingRepository


class ArgenpropParser(BaseParser):
    base_info_class = 'listing__item'
    url_base = "https://www.argenprop.com"

    base_info_tag = "div"
    link_regex = "a.card"
    price_regex = "p.card__price"
    description_regex = "p.card__title--primary"
    location_regex = "p.card__address"
    title_regex = "h2.card__title, p.card__title--primary"

    def extract_data(self) -> Set[Posting]:
        """Extracting data and returning list of objects"""
        postings = set()
        base_info_soaps = self.soup.find_all(
            self.base_info_tag, class_=self.base_info_class)

        for base_info_soap in base_info_soaps:
            link_container = base_info_soap.select_one(self.link_regex)
            price_container = base_info_soap.select_one(self.price_regex)
            description_container = base_info_soap.select_one(self.description_regex)
            location_container = base_info_soap.select_one(self.location_regex)
            title_container = base_info_soap.select_one(self.title_regex)

            # require link and title; description/location may be missing on listing page
            if not (link_container and title_container):
                continue

            href = "{}{}".format(self.url_base, link_container.get("href", ""))
            title = self.sanitize_text(title_container.get_text())
            sha = self.get_id(href)
            price = self.sanitize_text(price_container.get_text()) if price_container else ''
            description = self.sanitize_text(description_container.get_text())
            location = self.sanitize_text(location_container.get_text())

            posting_repository = PostingRepository()
            if posting_repository.get_posting_by_sha(sha):
                continue

            new_posting = Posting(
                sha=sha,
                url=href,
                title=title,
                price=price,
                description=description,
                location=location,
            )
            postings.add(new_posting)

        return postings
