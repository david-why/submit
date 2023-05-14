from typing import TYPE_CHECKING, Dict, Optional, Tuple, Type, Union

from .submitters import NAMES, SUBMITTERS

if TYPE_CHECKING:
    from .base import Language, Problem, Submission, SubmitterBase

__all__ = ['Submitter', 'NotLoggedInError']


class NotLoggedInError(Exception):
    pass


class Submitter:
    def __init__(self):
        self._ojs: Dict[Type['SubmitterBase'], 'SubmitterBase'] = {}

    def dump(self) -> dict:
        return {'ojs': {k.name: v.dump() for k, v in self._ojs.items()}}

    def load(self, data: dict) -> None:
        ojs = data['ojs']
        for k, v in ojs.items():
            cls = NAMES[k]
            obj = self._ojs[cls] = cls()
            obj.load(v)

    def get_oj(self, oj: Union[Type['SubmitterBase'], str]) -> 'SubmitterBase':
        if isinstance(oj, str):
            oj = NAMES[oj]
        if oj in self._ojs:
            return self._ojs[oj]
        return self._ojs.setdefault(oj, oj())

    def login(
        self, oj: Union[Type['SubmitterBase'], str], username: str, password: str
    ) -> bool:
        obj = self.get_oj(oj)
        return obj.login(username, password)

    def logout(self, oj: Union[Type['SubmitterBase'], str]) -> bool:
        obj = self.get_oj(oj)
        return obj.logout()

    def get_problem(
        self, oj: Union[Type['SubmitterBase'], str], problem: str
    ) -> Optional['Problem']:
        obj = self.get_oj(oj)
        if obj.require_view_login and not obj.logged_in:
            raise NotLoggedInError()
        return obj.get_problem(problem)

    def search_problem(self, code: str) -> Optional[Tuple[Type['SubmitterBase'], str]]:
        for cls in SUBMITTERS:
            problem = cls.search_problem(code)
            if problem:
                return cls, problem

    def parse_problem_url(
        self, url: str
    ) -> Optional[Tuple[Type['SubmitterBase'], str]]:
        for cls in SUBMITTERS:
            problem = cls.parse_problem_url(url)
            if problem:
                return cls, problem

    def submit(
        self,
        oj: Union[Type['SubmitterBase'], str],
        problem: str,
        code: str,
        lang: 'Language',
    ) -> str:
        obj = self.get_oj(oj)
        if obj.require_submit_login and not obj.logged_in:
            raise NotLoggedInError()
        return obj.submit(problem, code, lang)

    def get_submission(
        self, oj: Union[Type['SubmitterBase'], str], id: str
    ) -> Optional['Submission']:
        return self.get_oj(oj).get_submission(id)
