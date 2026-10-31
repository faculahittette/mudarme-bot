'''Apto credito segun el texto del aviso (avisos sin la marca del sitio).'''
import pytest
from pydantic import ValidationError

from main import (
    APTO_POR_DESCRIPCION,
    Config,
    Search,
    build_searches,
    describe_search,
    load_config_dict,
)
from posting_app.apto_credito_service import BADGE, AptoCreditoPorDescripcionService
from posting_app.database import Posting
from scraper_app.apto_credito import Veredicto, clasificar, texto_del_aviso
from telegram_app.services import TelegramService


# ------------------------------------------------------------ Clasificador
# Frases reales de avisos de Zonaprop, Argenprop y Mercado Libre (oct-2026).

@pytest.mark.parametrize('texto', [
    'Departamento tipo DúPLEX 3 AMBIENTES CON BALCóN | APTO CRéDITO Granaderos 792',
    'Excelente PH sin expensas RECICLADO APTO CREDITO PH en planta alta',
    'Listo para mudarse, escritura inmediata. Apto crédito Bancario.',
    'Cochera en PB de fácil acceso, fija y cubierta. APTO CRÉDITO HIPOTECARIO',
    'Apto profesional. Apto crédito. Ph de 4 ambientes en 2 plantas',
    'Ph en venta en directorio al 2700 | apto crédito, terraza',
    'Apto créditoSí',  # fila de caracteristicas de Mercado Libre
])
def test_dice_apto(texto):
    assert clasificar(texto) is Veredicto.SI


@pytest.mark.parametrize('texto', [
    'en living comedor y habitaciones. No es apto crédito, las medidas son aproximadas',
    '120m2 totales, 90 m2 cubiertos. NO apto credito. 2do piso por escalera.',
    'DEPARTAMENTO TODO ELÉCTRICO Y NO APTO CRÉDITO Distribución de ambientes',
    'Super Luminoso. No es apto credito! Ubicado a tan solo 3 cuadras',
    'Tiene cochera? No. Es apto crédito? No, la operación es de contado',
    'Apto créditoNo',  # fila de caracteristicas de Mercado Libre
    'Apto crédito: no',
    'No acepta crédito hipotecario',
])
def test_dice_que_no(texto):
    assert clasificar(texto) is Veredicto.NO


@pytest.mark.parametrize('texto', [
    'Apto crédito a consultar',
    'Consultar si es apto crédito',
    'Apto crédito: en trámite',
    'Hermoso 3 ambientes, apto profesional, muy luminoso',
    '',
])
def test_duda_o_no_lo_menciona_no_se_manda(texto):
    assert clasificar(texto) is Veredicto.DESCONOCIDO


# ------------------------------------------- Texto de la pagina del aviso

def test_zonaprop_lee_titulo_y_descripcion_pero_no_avisos_similares():
    html = '''<h1>Depto 3 amb Caballito</h1>
      <div id="reactDescription">Luminoso. Apto crédito.</div>
      <div class="similares">Otro depto NO apto crédito</div>'''
    assert texto_del_aviso('zonaprop', html) == 'Depto 3 amb Caballito Luminoso. Apto crédito.'


def test_argenprop_lee_caracteristicas():
    html = '''<h1>Venta depto</h1><div class="section-description--content">Lindo</div>
      <ul class="property-features"><li>Cant. Ambientes: 3</li><li>Apto Crédito</li></ul>'''
    assert clasificar(texto_del_aviso('argenprop', html)) is Veredicto.SI


def test_mercadolibre_lee_la_tabla_de_caracteristicas():
    html = '''<h1>Depto Flores</h1><p class="ui-pdp-description__content">Muy lindo</p>
      <table><tr><th>Apto crédito</th><td>No</td></tr></table>'''
    assert clasificar(texto_del_aviso('mercadolibre', html)) is Veredicto.NO


# ------------------------------------------------------------- Servicio

class _Scraper:
    complete = True
    publication_in_detail_page = True

    def __init__(self, postings, pages):
        self._postings, self._pages, self.visited = postings, pages, []

    def get_postings_from_scraper(self):
        return set(self._postings)

    def fetch_detail(self, url):
        self.visited.append(url)
        return self._pages.get(url)


class _Postings:
    def __init__(self, known=()):
        self.known, self.created = set(known), []

    def get_postings_by_sha(self, shas):
        return {s: object() for s in shas if s in self.known}

    def create_posting(self, posting):
        self.created.append(posting)
        return True


class _Checks:
    def __init__(self, checked=()):
        self.checked, self.saved = set(checked), {}

    def checked_shas(self, shas):
        return {s for s in shas if s in self.checked}

    def save(self, sha, url, veredicto):
        self.saved[sha] = veredicto


def _p(sha):
    return Posting(sha=sha, url=f'https://z/{sha}', title=sha)


def _run(postings, pages, known=(), checked=()):
    scraper, repo, checks = _Scraper(postings, pages), _Postings(known), _Checks(checked)
    ok = AptoCreditoPorDescripcionService('zonaprop', scraper, repo, checks).scrap_and_create_postings()
    return ok, scraper, repo, checks


def _page(desc):
    return f'<h1>T</h1><div id="reactDescription">{desc} Publicado hace 3 días</div>'


def test_solo_guarda_para_enviar_los_que_dicen_apto():
    ok, _, repo, checks = _run(
        [_p('si'), _p('no'), _p('nada')],
        {'https://z/si': _page('Apto crédito.'), 'https://z/no': _page('No apto crédito'),
         'https://z/nada': _page('Luminoso')},
    )
    assert ok is True
    assert [p.sha for p in repo.created] == ['si']
    assert repo.created[0].badge == BADGE
    assert repo.created[0].published == 'hace 3 días'
    assert checks.saved == {'si': 'si', 'no': 'no', 'nada': 'desconocido'}


def test_no_entra_a_avisos_ya_guardados_ni_ya_revisados():
    _, scraper, _, _ = _run([_p('guardado'), _p('revisado'), _p('nuevo')],
                            {'https://z/nuevo': _page('')}, known={'guardado'}, checked={'revisado'})
    assert scraper.visited == ['https://z/nuevo']


def test_si_la_pagina_no_responde_lo_reintenta_en_otra_corrida():
    _, _, repo, checks = _run([_p('caido')], {})
    assert repo.created == [] and checks.saved == {}


def test_pagina_sin_texto_no_se_marca_como_revisada():
    # Ej: pantalla anti-robots o el sitio cambio su HTML.
    _, _, repo, checks = _run([_p('raro')], {'https://z/raro': '<html>JavaScript is disabled</html>'})
    assert repo.created == [] and checks.saved == {}


# ------------------------------------------------- Config y busquedas

def test_build_searches_agrega_las_busquedas_sin_marca_al_final():
    config = Config(bot_token='t', chat_room='c', zonaprop_full_url='z-apto',
                    apto_credito_por_descripcion={'zonaprop': 'z-todo', 'argenprop': ['a1', 'a2']})
    searches = build_searches(config)
    assert searches[0] == Search('zonaprop', 'z-apto')
    assert [(s.site, s.url, s.kind) for s in searches[1:]] == [
        ('zonaprop', 'z-todo', APTO_POR_DESCRIPCION),
        ('argenprop', 'a1', APTO_POR_DESCRIPCION),
        ('argenprop', 'a2', APTO_POR_DESCRIPCION),
    ]


def test_sitio_no_soportado_es_error_de_config():
    with pytest.raises(ValidationError):
        Config(bot_token='t', chat_room='c', apto_credito_por_descripcion={'remax': 'r'})


def test_skip_sites_tambien_apaga_la_busqueda_sin_marca(tmp_path):
    searches = tmp_path / 'searches.yaml'
    searches.write_text('apto_credito_por_descripcion:\n  argenprop: "a"\n  zonaprop: "z"\n')
    data = load_config_dict(tmp_path / 'x.yaml', searches, {'SKIP_SITES': 'argenprop'})
    assert data['apto_credito_por_descripcion'] == {'zonaprop': 'z'}


def test_la_alerta_distingue_la_busqueda_sin_marca():
    search = Search('argenprop', 'https://a/ph/venta', kind=APTO_POR_DESCRIPCION)
    assert describe_search(search) == 'argenprop (sin marca apto credito) · /ph/venta'


def test_el_mensaje_muestra_la_etiqueta_debajo_del_titulo():
    posting = Posting(sha='a', url='https://x', title='Depto', price='USD 1', location='L', badge=BADGE)
    lines = TelegramService('t', 'c').format_posting_to_message(posting).split('\n')
    assert lines[:2] == ['<b>Depto</b>', f'<b>{BADGE}</b>']
