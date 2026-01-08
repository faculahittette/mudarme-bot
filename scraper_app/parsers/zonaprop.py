from typing import Set

from bs4 import BeautifulSoup

from .base import BaseParser
from posting_app.database import Posting, PostingRepository


class ZonapropParser(BaseParser):
    base_info_class = 'postingCardLayout-module__posting-card-container'
    base_info_tag = 'div'
    link_regex = 'h3.postingCard-module__posting-description a'
    price_regex = 'div.postingPrices-module__price'
    description_regex = 'h3.postingCard-module__posting-description'
    location_regex = 'h2.postingLocations-module__location-text'
    features_regex = 'span.postingMainFeatures-module__posting-main-features-span'
    _base_url = 'https://www.zonaprop.com.ar'

    def extract_data(self) -> Set[Posting]:
        '''Extracting data and returning list of postings'''
        postings = set()
        base_info_soaps = self.soup.find_all(
            self.base_info_tag, class_=self.base_info_class)

        for base_info_soap in base_info_soaps:
            link_container = base_info_soap.select_one(self.link_regex)
            price_container = base_info_soap.select_one(self.price_regex)
            description_container = base_info_soap.select_one(self.description_regex)
            location_container = base_info_soap.select_one(self.location_regex)

            if not (link_container and description_container and location_container):
                # price may be 'Consultar precio' or missing, but link/description/location are required
                continue

            href = '{}{}'.format(
                self._base_url,
                link_container.get('href', ''),
            )

            # Short title: take first line or first 100 chars
            raw_title = link_container.get_text(separator=' ').strip()
            # sometimes Zonaprop uses long descriptions; split on 'Descripción' to keep concise
            if 'Descripción' in raw_title:
                raw_title = raw_title.split('Descripción')[0]
            title = self.sanitize_text(raw_title)[:100]

            sha = self.get_id(href)
            price = self.sanitize_text(price_container.get_text()) if price_container else ''

            # Build brief description from features (m2, ambs) if present
            features = [self.sanitize_text(f.get_text()) for f in base_info_soap.select(self.features_regex)]
            if features:
                description = ' | '.join(features)
            else:
                # fallback: short excerpt of the long description
                description = self.sanitize_text(description_container.get_text())[:140]

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
