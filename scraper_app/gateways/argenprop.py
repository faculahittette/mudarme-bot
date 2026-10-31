from .base import BaseGateway


class ArgenpropGateway(BaseGateway):
    # Argenprop responde 202 (pantalla anti-robots) si le pegamos seguido:
    # un intento mas y esperas mas largas (10s, 20s) suelen alcanzar.
    attempts = 3
    retry_wait_seconds = 10
    # 20 avisos por pagina: si una trae menos, no pedimos la siguiente (ese
    # pedido de mas es justo el que suele comerse el 202).
    page_size = 20

    def __init__(self):
        self._name = 'Argenprop'
