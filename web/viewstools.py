from typing import Callable


class View:
    def __init__(self, view_maker, mime_type):
        self.mime_type = mime_type
        self._view_maker = view_maker

    def apply(self, data):
        return self._view_maker(data)


class ViewHolder:
    def __init__(self):
        self._views = {}

    def add_view(self, _id: str, view_obj: View):
        if not self._views.get(_id):
            self._views[_id] = {}
        self._views[_id][view_obj.mime_type] = view_obj

    def get_view(self, _id, mime_type):
        return self._views[_id][mime_type]



