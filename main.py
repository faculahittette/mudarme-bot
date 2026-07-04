import yaml
from time import sleep
from typing import List, Optional, Union

import typer
from pydantic import BaseModel
from pydantic import ValidationError
from rich.console import Console
from rich.progress import track

from posting_app.database import create_db_and_tables, PostingRepository
from posting_app.services import PostingServiceFactory
from telegram_app.services import TelegramService

console = Console()


Urls = Optional[Union[str, List[str]]]


class Config(BaseModel):
    pages: Optional[int] = 3
    sleep_time: Optional[int] = 5
    bot_token: str
    chat_room: str
    persist: Optional[bool] = False
    zonaprop_base_url: Optional[str] = None
    # Cada *_full_url acepta una URL (string) o varias (lista de strings),
    # util por ejemplo para sumar una busqueda "a estrenar" ademas de la normal.
    zonaprop_full_url: Urls = None
    argenprop_full_url: Urls = None
    mercadolibre_full_url: Urls = None
    la_voz_full_url: Urls = None
    properati_full_url: Urls = None
    remax_full_url: Urls = None


def as_url_list(urls: Urls) -> List[str]:
    '''Normaliza el campo de config (None / str / list) a una lista de URLs.'''
    if not urls:
        return []
    if isinstance(urls, str):
        return [urls]
    return list(urls)


def main(config_path: str):
    # LOAD CONFIG
    with open(config_path) as config_json:
        config_dict = yaml.safe_load(config_json)

    try:
        config = Config(**config_dict)
    except ValidationError as ex:
        console.log(
            '[bold u]ERROR[/bold u]: Config error.\n', ex, style='red'
        )
        return
    console.log('Configuration read correctly', style='italic bold green')
    
    # LOAD DATABASE
    create_db_and_tables()
    console.log('Database loaded', style='italic bold green')

    # Cada entrada mapea un sitio a su builder; cada sitio puede tener varias URLs.
    site_builders = [
        (config.zonaprop_full_url, PostingServiceFactory.build_for_zonaprop),
        (config.argenprop_full_url, PostingServiceFactory.build_for_argenprop),
        (config.mercadolibre_full_url, PostingServiceFactory.build_for_mercadolibre),
        (config.la_voz_full_url, PostingServiceFactory.build_for_la_voz),
        (config.properati_full_url, PostingServiceFactory.build_for_properati),
        (config.remax_full_url, PostingServiceFactory.build_for_remax),
    ]

    while(True):
        # SCRAP POSTINGS
        for urls, build_posting_service in site_builders:
            for url in as_url_list(urls):
                posting_service = build_posting_service(
                    pages=config.pages,
                    full_url=url,
                )
                posting_service.scrap_and_create_postings()

        console.log('Postings scrapped', style='italic bold green')

        # SEND POSTINGS
        posting_repository = PostingRepository()
        unsent_postings = posting_repository.get_unsent_postings()

        telegram_service = TelegramService(
            bot_token=config.bot_token,
            chat_room=config.chat_room,
        )
        console.log(f'About to send [u]{len(unsent_postings)}[/u] postings')
        for posting in track(unsent_postings, description='Sending postings...'):
            # Try sending with automatic retries and backoff (respects Telegram's retry_after when detected)
            ok = telegram_service.send_with_retries(posting, max_retries=3, backoff_base=2)
            if ok:
                posting_repository.set_posting_as_sent(posting.sha)
            else:
                console.log(
                    (
                        '[bold u]WARNING[/bold u]: '
                        f'Unable to send {posting.title} after retries. '
                        'It will be retried later automatically.'
                    ),
                    style='yellow'
                )
        console.log('Postings sent', style='italic bold green')

        if not config.persist:
            break
        
        sleep(config.sleep_time)


if __name__ == '__main__':
    typer.run(main)