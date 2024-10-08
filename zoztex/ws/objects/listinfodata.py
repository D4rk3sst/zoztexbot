"""Module for Quotex Candles websocket object."""

from zoztex.ws.objects.base import Base


class ListInfoData(Base):
    """Class for Quotex Candles websocket object."""

    def __init__(self):
        super(ListInfoData, self).__init__()
        self.__name = "listInfoData"
        self.listinfodata_dict = {}

    def set(self, id_number, win, game_state):
        self.listinfodata_dict[id_number] = {"win": win, "game_state": game_state}

    def delete(self, id_number):
        self.listinfodata_dict.pop(id_number, None)

    def get(self, id_number):
        return self.listinfodata_dict.get(id_number, None)
