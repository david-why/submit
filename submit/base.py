import html
import re
import time
from abc import ABC, abstractmethod
from enum import IntEnum, auto
from typing import Any, Dict, List, Optional, Tuple, overload

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from .util import get_text

__all__ = [
    'Language',
    'LANGUAGES',
    'Verdict',
    'TextType',
    'Problem',
    'Case',
    'Submission',
    'SubmitterBase',
]


class Language(IntEnum):
    C__ = 1
    PYTHON3 = 2
    PY3 = 2


Language._value2member_map_.update({'C++': Language.C__})
LANGUAGES = {'C++': Language.C__, 'Python 3': Language.PYTHON3}


class Verdict(IntEnum):
    UNKNOWN = -1
    ACCEPTED = 0
    OK = 0
    WRONG_ANSWER = 1
    TIME_LIMIT_EXCEEDED = 2
    RUNTIME_ERROR = 3
    MEMORY_LIMIT_EXCEEDED = 4
    COMPILATION_ERROR = 5
    IDLENESS_LIMIT_EXCEEDED = 6
    OTHER_PASS = 256
    OTHER_FAIL = 257


class TextType(IntEnum):
    TEXT = auto()
    MARKDOWN = auto()
    HTML = auto()


class Problem:
    _MATH_RE = re.compile(r'(?P<s>\${1,3})(.*?)(?P=s)')
    _VAR_RE = re.compile(r'<var>(.*?)</var>')

    def __init__(
        self,
        id: str,
        text: str,
        texttype: TextType,
        cases: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        self.id = id
        self.text = text
        self.texttype = texttype
        self.cases = cases

    def get_html(self) -> Optional[str]:
        if self.texttype == TextType.HTML:
            return self.text
        if self.texttype == TextType.TEXT:
            return str(html.escape(self.text)).replace('\n', '<br/>')
        r = requests.post(
            'https://api.github.com/markdown', json={'text': self.text}, timeout=10
        )
        return r.text

    def get_markdown(self):
        if self.texttype in [TextType.TEXT, TextType.MARKDOWN]:
            return self.text
        try:
            math_re = self._MATH_RE
            import markdownify

            class Converter(markdownify.MarkdownConverter):
                def convert_div(self, el, text, convert_as_inline):
                    if convert_as_inline:
                        return text
                    clazz = el.attrs.get('class', [])
                    if 'section-title' in clazz:
                        return self.convert_h3(el, text, convert_as_inline)
                    if 'title' in clazz:
                        return self.convert_h2(el, text, convert_as_inline)
                    if 'property-title' in clazz:
                        return self.convert_b(el, text, convert_as_inline) + ' '
                    return text + '\n'

                def convert_code(self, el, text, convert_as_inline):
                    if math_re.match(text):
                        return text
                    cur = el
                    while cur:
                        if cur.name.lower() == 'pre':
                            return text
                        cur = cur.parent
                    return super().convert_code(el, text, convert_as_inline)

            def traverse(node, _pre=False):
                for c in node.children:
                    if isinstance(c, Tag):
                        if c.name.lower() == 'var':
                            if _pre:
                                c.insert_after(NavigableString('$%s$' % c.text))
                            else:
                                c.insert_after(
                                    BeautifulSoup(
                                        '<code>$%s$</code>' % c.text, 'html.parser'
                                    ).select_one('code')
                                )
                            c.extract()
                        elif c.name.lower() == 'pre':
                            traverse(c, True)
                        else:
                            traverse(c, _pre)
                    else:
                        continue

            conv = Converter(heading_style='atx')
            s = BeautifulSoup(
                '<div>%s</div>' % math_re.sub(r'<code>$\2$</code>', self.text),
                'html.parser',
            ).select_one('div')
            traverse(s)
            return conv.convert(str(s))
        except:
            return self.get_text()

    def get_text(self):
        if self.texttype in [TextType.TEXT, TextType.MARKDOWN]:
            return self.text
        return get_text(BeautifulSoup(self.text, 'html.parser')).strip()

    def get_as_type(self, texttype: TextType) -> str:
        return {
            TextType.TEXT: self.get_text,
            TextType.MARKDOWN: self.get_markdown,
            TextType.HTML: self.get_html,
        }[texttype]()


class Case:
    def __init__(
        self,
        time: float,
        memory: float,
        input: Optional[str] = None,
        output: Optional[str] = None,
        answer: Optional[str] = None,
        verdict: Optional[Verdict] = None,
        message: Optional[str] = None,
    ) -> None:
        self.time = time
        self.memory = memory
        self.input = input
        self.output = output
        self.answer = answer
        self.verdict = verdict
        self.message = message

    def to_json(self):
        data = {'time': self.time, 'memory': self.memory}
        for k in ['input', 'output', 'answer', 'message']:
            v = getattr(self, k)
            if v is not None:
                data[k] = v
        if self.verdict is not None:
            data['verdict'] = self.verdict.name
        return data


class Submission:
    def __init__(
        self,
        id: str,
        verdict: Verdict,
        problem: str,
        score: int,
        code: Optional[str] = None,
        time: Optional[float] = None,
        memory: Optional[float] = None,
        cases: Optional[List[Case]] = None,
        data: Optional[Any] = None,
    ) -> None:
        self.id = id
        self.verdict = verdict
        self.problem = problem
        self.score = score
        self.code = code
        self.time = time
        self.memory = memory
        self.cases = cases
        self.data = data

    def to_json(self):
        return {
            'id': self.id,
            'verict': self.verdict.name,
            'ac': not (self.verdict.value & 255),
            'problem': self.problem,
            'score': self.score,
            'time': self.time,
            'memory': self.memory,
            'cases': [x.to_json() for x in self.cases or []],
            'data': self.data,
        }


class Wrapper(requests.Session):
    def _get(self, *args, **kwargs):
        print('GET', args, kwargs)
        return super().get(*args, **kwargs)

    def _post(self, *args, **kwargs):
        print('POST', args, kwargs)
        return super().post(*args, **kwargs)


class SubmitterBase(ABC):
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
    }
    name: str  # this is defined in subclasses
    require_submit_login = True
    require_view_login = False

    def __init__(self) -> None:
        self.session = Wrapper()
        self.session.headers.update(self.HEADERS)

    def __getstate__(self):
        return self.session

    def __setstate__(self, state):
        self.session = state

    @classmethod
    @abstractmethod
    def parse_problem_url(cls, url: str) -> Optional[str]:
        ...

    @classmethod
    @abstractmethod
    def get_problem_url(cls, id: str) -> Optional[str]:
        ...

    @classmethod
    def search_problem(cls, text: str) -> Optional[str]:
        return

    @abstractmethod
    def login(self, username: str, password: str) -> bool:
        ...

    @abstractmethod
    def logout(self) -> bool:
        ...

    @property
    @abstractmethod
    def logged_in(self) -> bool:
        ...

    @abstractmethod
    def get_problem(self, id: str) -> Optional[Problem]:
        ...

    @abstractmethod
    def submit(self, id: str, code: str, lang: Language) -> str:
        ...

    @abstractmethod
    def get_submission(self, id: str) -> Optional[Submission]:
        ...

    @overload
    def wait_submission(self, id: str, timeout: Optional[int] = ...) -> Submission:
        ...

    @overload
    def wait_submission(self, id: str, timeout: int) -> Submission:
        ...

    def wait_submission(self, id, timeout=-1) -> Submission:
        start = time.time()
        while True:
            sub = self.get_submission(id)
            if sub is not None:
                return sub
            time.sleep(1)
            if timeout > 0 and time.time() - start > timeout:
                return

    def dump(self) -> Dict[str, Any]:
        return {'cookies': dict(self.session.cookies)}

    def load(self, data: Dict[str, Any]) -> None:
        self.session.cookies.clear()
        self.session.cookies.update(data['cookies'])
