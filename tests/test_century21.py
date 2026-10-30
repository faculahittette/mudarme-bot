import json
from datetime import date

from main import Config, FilteredSearchConfig, build_searches
from scraper_app.parsers.century21 import Century21Listing, Century21Parser


def _item(pid, **kw):
    base = {
        'property_id': pid, 'title': f'Depto {pid}', 'prop_type': 'departamento',
        'status': 'active', 'currency_id': 'USD', 'price': '195000.00', 'price_hidden': False,
        'construction_year': 2020, 'rooms': 3, 'bedrooms': 2, 'covered_square_meters': '70.50',
        'addr_subarea': 'Caballito Norte', 'addr_district': 'Caballito',
        'addr_street': 'Arengreen', 'addr_number': '1400',
        'created_at': '2026-10-20T21:35:17.338Z', 'description': '$22',
    }
    return {**base, **kw}


def _html(items):
    '''Payload RSC como lo manda el sitio: partido en dos chunks.'''
    rsc = '13:[["$","$L21","q",{"initialProperties":' + json.dumps(items) + ',"count":85}]]'
    half = len(rsc) // 2
    chunks = ''.join(
        '<script>self.__next_f.push([1,{}])</script>'.format(json.dumps(part))
        for part in (rsc[:half], rsc[half:])
    )
    return f'<html><body>{chunks}</body></html>'


def _parser():
    cfg = FilteredSearchConfig(
        tipos=['departamento', 'ph'], antiguedad_max_anos=10,
        antiguedad_max_anos_por_tipo={'ph': 20}, ambientes_min=3,
        superficie_cubierta_min_m2=65,
    )
    return Century21Parser(cfg.build_filter())


def _parse(items):
    parser = _parser()
    parser.get_soup_object(html=_html(items))
    return parser, {p.url.rsplit('/', 1)[-1]: p for p in parser.extract_data()}


def test_parses_listing_from_rsc_payload():
    _, postings = _parse([_item('503796')])
    p = postings['503796']
    assert p.url == 'https://www.century21.com.ar/propiedades/503796'
    assert p.title == 'Depto 503796'
    assert p.price == 'USD 195,000'
    assert p.location == 'Caballito Norte · Arengreen 1400'
    assert '70 m2 cub' in p.description and '3 amb' in p.description
    assert p.published  # "hace N días" desde created_at


def test_local_filters_age_and_availability():
    parser, postings = _parse([
        _item('nuevo'),
        _item('viejo', construction_year=1980),
        _item('ph-2010', prop_type='ph', construction_year=2010),   # PH hasta 20 anos
        _item('sin-anio', construction_year=None),                   # dato faltante: pasa
        _item('reservado', status='reserved'),
        _item('con-oferta', status='under_offer'),
    ])
    assert set(postings) == {'nuevo', 'ph-2010', 'sin-anio'}
    # La paginacion cuenta todo lo que vino, no solo lo que paso los filtros.
    assert len(parser.page_keys) == 6


def test_hidden_price():
    _, postings = _parse([_item('x', price_hidden=True)])
    assert postings['x'].price == 'Consultar precio'


def test_empty_or_broken_page():
    for html in ('', '<html>sin payload</html>', _html([])):
        parser = _parser()
        parser.get_soup_object(html=html)
        assert parser.extract_data() == set()
        assert parser.page_keys == set()


def test_age_from_construction_year():
    listing = Century21Listing.from_api(_item('a', construction_year=2016), today=date(2026, 10, 30))
    assert listing.antiguedad_anos == 10
    assert Century21Listing.from_api(_item('b', construction_year=0)).antiguedad_anos is None


def test_build_searches_injects_filtered_parser():
    config = Config(bot_token='t', chat_room='c', zonaprop_full_url=['z1', 'z2'],
                    century21={'url': 'c21?page={}', 'antiguedad_max_anos': 10})
    searches = build_searches(config)
    assert [(s, u) for s, u, _ in searches] == [('zonaprop', 'z1'), ('zonaprop', 'z2'), ('century21', 'c21?page={}')]
    assert isinstance(searches[-1][2], Century21Parser)
