from .base import BaseGateway


class ArgenpropGateway(BaseGateway):
    # Argenprop responde 202 (pantalla anti-robots) si le pegamos seguido:
    # un intento mas y esperas mas largas (10s, 20s) suelen alcanzar.
    attempts = 3
    retry_wait_seconds = 10
    # 20 avisos por pagina: si una trae menos, no pedimos la siguiente (ese
    # pedido de mas es justo el que suele comerse el 202).
    page_size = 20
    # Ritmo de persona y cookies entre paginas, como un navegador.
    min_interval_seconds = 4
    reuse_session = True

    def __init__(self):
        self._name = 'Argenprop'

    def page_param(self, page: int) -> str:
        '''Sufijo de pagina para el `{}` de la URL: nada en la 1 y `&pagina-N`
        desde la 2. Es la forma canonica del sitio: `&pagina-1` (o el formato
        viejo `?con-aptocredito`) responde con una redireccion, o sea dos
        pedidos por pagina.'''
        return '' if page == 1 else f'&pagina-{page}'
