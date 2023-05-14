import importlib

from submit.base import SubmitterBase

__all__ = ['SUBMITTERS', 'NAMES']

_files = ['atcoder', 'codeforces', 'cses', 'luogu', 'usaco_contest', 'usaco', 'vjudge']
SUBMITTERS = []
NAMES = {}
for _file in _files:
    _module = importlib.import_module('.' + _file, 'submit.submitters')
    for _name, _obj in vars(_module).items():
        if (
            _name[0].isupper()
            and isinstance(_obj, type)
            and SubmitterBase in _obj.mro()
            and _obj is not SubmitterBase
        ):
            globals()[_name] = _obj
            __all__.append(_name)
            SUBMITTERS.append(_obj)
            NAMES[_obj.name] = _obj
