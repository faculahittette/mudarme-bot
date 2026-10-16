from posting_app.database import Posting
from scraper_app.parsers.zonaprop import ZonapropParser
from telegram_app.services import TelegramService


def test_zonaprop_title_comes_from_url_slug():
    url = ('https://www.zonaprop.com.ar/propiedades/clasificado/'
           'veclapin-emprendimiento-en-floresta-financiacion-entrega-57003476.html')
    assert ZonapropParser._title_from_url(url) == 'Emprendimiento en floresta financiacion entrega'


def test_message_always_has_visible_link_even_without_title():
    posting = Posting(sha='x', url='https://example.com/a?b=1&c=2', title='',
                      price='USD 210.000', location='Flores', description='3 amb.')
    msg = TelegramService(bot_token='t', chat_room='c').format_posting_to_message(posting)
    assert '<a href="https://example.com/a?b=1&amp;c=2">Ver publicación</a>' in msg
    assert '<b>Propiedad en venta</b>' in msg
