

class ImageInspect(object):
    def __init__(self, service=None, image=None, Author=None, Created=None, Id=None, Config=None, RepoTags=None, **kwargs):
        self._service = service
        self._image = image
        self._author = Author
        self._created = Created[:19] if Created else ''
        self._id = Id.split(':')[-1][:12] if Id else ''
        self._labels = Config.get('Labels', None) if Config else None
        self._match = ''
        if RepoTags:
            if image not in RepoTags:
                self._match += '!(NOT MATCH)'
        else:
            if Id:
                self._match += '!(NOT MATCH)'

    def __call__(self, *args, **kwargs):
        _dict = {}
        _dict['service'] = self._service
        _dict['image'] = self._image
        _dict['Author'] = self._author
        _dict['Created'] = self._created
        _dict['Id'] = self._id
        _dict['Labels'] = ''
        _dict['Match'] = self._match
        if self._labels:
            for k,v in self._labels.items():
                v = v[:20]
                _dict['Labels'] += '%s: %s \n'%(k,v)
            _dict['Labels'] = _dict['Labels'].strip('\n')
        return _dict
