from .base import BaseGateway


class RoomixGateway(BaseGateway):
    '''Roomix (roomix.ai): agregador con paginas `/buscar/...?page=N`.'''

    def __init__(self):
        self._name = 'Roomix'
