import os
import yaml
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Tuple, Union

import typer
from pydantic import BaseModel
from pydantic import ValidationError
from rich.console import Console
from rich.progress import track

from posting_app.database import (
    PostingRepository,
    configure_database,
    create_db_and_tables,
    database_label,
)
from posting_app.services import PostingServiceFactory
from scraper_app.filters import (
    AndFilter,
    ExcluirReservadasFilter,
    ListingFilter,
    MaxAntiguedadFilter,
    MinAmbientesFilter,
    MinSuperficieCubiertaFilter,
    PublicadaValidaFilter,
    TiposPermitidosFilter,
)
from scraper_app.parsers import BaseParser, BnaParser, Century21Parser
from telegram_app.services import TelegramService
from run_log import tee_output_to

console = Console()


Urls = Optional[Union[str, List[str]]]


class FilteredSearchConfig(BaseModel):
    '''Busqueda de un sitio cuya URL no permite todos nuestros filtros (BNA,
    Century 21): la URL filtra lo que puede y el resto se aplica localmente.
    Campo en null = no filtra.'''
    url: Urls = None
    tipos: List[str] = []
    antiguedad_max_anos: Optional[int] = None
    antiguedad_max_anos_por_tipo: Dict[str, int] = {}
    ambientes_min: Optional[int] = None
    superficie_cubierta_min_m2: Optional[float] = None
    excluir_reservadas: bool = True

    def build_filter(self) -> ListingFilter:
        filters: List[ListingFilter] = [PublicadaValidaFilter()]
        if self.tipos:
            filters.append(TiposPermitidosFilter(self.tipos))
        if self.antiguedad_max_anos is not None:
            filters.append(MaxAntiguedadFilter(
                self.antiguedad_max_anos, self.antiguedad_max_anos_por_tipo
            ))
        if self.ambientes_min is not None:
            filters.append(MinAmbientesFilter(self.ambientes_min))
        if self.superficie_cubierta_min_m2 is not None:
            filters.append(MinSuperficieCubiertaFilter(self.superficie_cubierta_min_m2))
        if self.excluir_reservadas:
            filters.append(ExcluirReservadasFilter())
        return AndFilter(filters)


# Nombre historico, lo usan configs y tests.
BnaConfig = FilteredSearchConfig


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
    roomix_full_url: Urls = None
    bna: Optional[FilteredSearchConfig] = None
    century21: Optional[FilteredSearchConfig] = None
    # Base compartida (ej. Postgres en Neon) para correr desde varias compus
    # sin repetir envios. Vacio = SQLite local (scrapdep.db).
    database_url: Optional[str] = None


def as_url_list(urls: Urls) -> List[str]:
    '''Normaliza el campo de config (None / str / list) a una lista de URLs.'''
    if not urls:
        return []
    if isinstance(urls, str):
        return [urls]
    return list(urls)


ROOT = Path(__file__).resolve().parent

# Secretos que se pueden pasar por entorno (ej. secretos de GitHub Actions).
ENV_OVERRIDES = {
    'TELEGRAM_BOT_TOKEN': 'bot_token',
    'TELEGRAM_CHAT_ID': 'chat_room',
    'DATABASE_URL': 'database_url',
}
_SITE_KEYS = {
    'zonaprop': 'zonaprop_full_url',
    'argenprop': 'argenprop_full_url',
    'mercadolibre': 'mercadolibre_full_url',
    'la_voz': 'la_voz_full_url',
    'properati': 'properati_full_url',
    'remax': 'remax_full_url',
    'roomix': 'roomix_full_url',
    'bna': 'bna',
    'century21': 'century21',
}

# Sitios con filtros locales: el parser recibe el filtro armado desde el config.
_FILTERED_PARSERS = {
    'bna': BnaParser,
    'century21': Century21Parser,
}


Search = Tuple[str, str, Optional[BaseParser]]


def build_searches(config: 'Config') -> List[Search]:
    '''(sitio, url, parser inyectado o None) de cada busqueda configurada.'''
    searches: List[Search] = []
    for site, key in _SITE_KEYS.items():
        value = getattr(config, key)
        if not value:
            continue
        if site in _FILTERED_PARSERS:
            parser = _FILTERED_PARSERS[site](value.build_filter())
            searches.extend((site, url, parser) for url in as_url_list(value.url))
        else:
            searches.extend((site, url, None) for url in as_url_list(value))
    return searches


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding='utf-8') as fh:
        return yaml.safe_load(fh) or {}


def load_config_dict(config_path: Path, searches_path: Path, environ) -> dict:
    '''Arma la configuracion en capas (cada una pisa a la anterior):

    1. searches.yaml: busquedas compartidas, versionadas en el repo.
    2. config.yaml: secretos y ajustes locales (fuera de git, puede no existir).
    3. Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DATABASE_URL.
       SKIP_SITES=argenprop,... apaga sitios (ej. los que bloquean la nube).
    '''
    data = {**_read_yaml(searches_path), **_read_yaml(config_path)}
    for env_name, key in ENV_OVERRIDES.items():
        if environ.get(env_name):
            data[key] = environ[env_name]
    for site in filter(None, (environ.get('SKIP_SITES') or '').split(',')):
        data.pop(_SITE_KEYS.get(site.strip().lower(), ''), None)
    return data


def main(config_path: str = typer.Argument('config.yaml')):
    # LOAD CONFIG
    config_dict = load_config_dict(
        Path(config_path), ROOT / 'searches.yaml', os.environ
    )

    try:
        config = Config(**config_dict)
    except ValidationError as ex:
        console.log(
            '[bold u]ERROR[/bold u]: Config error.\n', ex, style='red'
        )
        raise typer.Exit(code=1)
    console.log('Configuration read correctly', style='italic bold green')
    
    # LOAD DATABASE
    configure_database(config.database_url)
    create_db_and_tables()
    console.log(f'Database loaded: {database_label()}', style='italic bold green')

    searches = build_searches(config)

    while(True):
        # SCRAP POSTINGS
        for site, url, parser in searches:
            posting_service = PostingServiceFactory.build(
                site=site,
                pages=config.pages,
                full_url=url,
                parser=parser,
            )
            # Un sitio caido o que cambio su HTML no debe frenar al resto.
            try:
                posting_service.scrap_and_create_postings()
            except Exception as ex:  # noqa: BLE001
                console.log(
                    f'[bold u]ERROR[/bold u]: fallo {site} ({url[:80]}...): {ex!r}',
                    style='red'
                )

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
            # Primero lo "reservo" en la base: si otra compu ya lo mando (o lo
            # esta mandando ahora), lo salteo. Asi no hay duplicados en el grupo.
            if not posting_repository.claim_for_sending(posting.sha):
                continue
            # Try sending with automatic retries and backoff (respects Telegram's retry_after when detected)
            ok = telegram_service.send_with_retries(posting, max_retries=3, backoff_base=2)
            if not ok:
                posting_repository.release_claim(posting.sha)
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
    # Todo lo que se ve en consola queda tambien en last_run.log, al lado de main.py.
    tee_output_to(Path(__file__).resolve().parent / 'last_run.log')
    typer.run(main)