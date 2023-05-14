import base64
import json
import re
import urllib.parse

from bs4 import BeautifulSoup

from ..base import Language, Problem, Submission, SubmitterBase, TextType, Verdict

__all__ = ['VJudgeSubmitter']


class VJudgeSubmitter(SubmitterBase):
    name = 'vjudge'

    RE = re.compile('https?://vjudge.net/problem/(.+)')
    PREC = {
        Language.PYTHON3: ['PyPy3', 'Pypy 3', 'Python3', 'Python 3'],
        Language.C__: [
            x + y + z
            for z in ['17', '14', '11']
            for y in [' ', '']
            for x in ['GNU G++', 'GNU C++', "C++"]
        ],
    }
    VERD = {
        'PE': Verdict.OTHER_FAIL,
        'WA': Verdict.WRONG_ANSWER,
        'TLE': Verdict.TIME_LIMIT_EXCEEDED,
        'MLE': Verdict.MEMORY_LIMIT_EXCEEDED,
        'OLE': Verdict.RUNTIME_ERROR,
        'RE': Verdict.RUNTIME_ERROR,
        'CE': Verdict.COMPILATION_ERROR,
    }

    def __init__(self):
        super().__init__()
        self._oj = self.session.get('https://vjudge.net/util/cfg').json()['remoteOJs']

    def __setstate__(self, state):
        if not hasattr(self, '_oj'):
            self.__init__()
        super().__setstate__(state)

    @classmethod
    def parse_problem_url(cls, url):
        match = cls.RE.match(url)
        if match:
            return match.group(1)

    @classmethod
    def get_problem_url(cls, id):
        return 'https://vjudge.net/problem/' + id

    @classmethod
    def search_problem(cls, text):
        match = cls.RE.search(text)
        if match:
            return match.group(1)

    def login(self, username, password):
        return (
            self.session.post(
                'https://vjudge.net/user/login',
                data={'username': username, 'password': password},
            ).text
            == 'success'
        )

    def logout(self):
        return self.session.post('https://vjudge.net/user/logout').status_code < 400

    @property
    def logged_in(self):
        return self.session.post('https://vjudge.net/user/checkLogInStatus').json()

    def get_problem(self, id):
        r = self.session.get(self.get_problem_url(id))
        s = BeautifulSoup(r.content, 'html.parser')
        dr = self.session.get(
            'https://vjudge.net' + s.select_one('#frame-description').attrs.get('src')
        )
        ds = BeautifulSoup(dr.content, 'html.parser')
        dj = json.loads(ds.select_one('textarea.data-json-container').text)
        text = ''
        for s in dj['sections']:
            fmt = s['value']['format']
            if fmt == 'MD':
                text += '# ' + s['title']
            elif fmt == 'HTML':
                text += '<h1>' + s['title'] + '</h1>'
            else:
                raise ValueError('Unknown format: %s' % fmt)
            text += s['value']['content']
        return Problem(id, text, TextType.HTML if fmt == 'HTML' else TextType.MARKDOWN)

    def submit(self, id, code, lang):
        typ, _, pid = id.partition('-')
        prec = self.PREC[lang]
        lang = (
            self._oj[typ].get('languages')
            or json.loads(
                BeautifulSoup(
                    self.session.get(self.get_problem_url(id)).content, 'html.parser'
                )
                .select_one('textarea[name="dataJson"]')
                .text
            )['languages']
        )
        found = False
        for p in prec:
            for lid, v in lang.items():
                if p.lower() in v.lower():
                    found = True
                    break
            if found:
                break
        if not found:
            raise NotImplementedError('Origin OJ not supported: %s' % typ)
        data = self.session.post(
            'https://vjudge.net/problem/submit',
            data={
                'method': '0',
                'language': lid,
                'open': 0,
                'source': base64.b64encode(urllib.parse.quote(code).encode()),
                'captcha': '',
                'oj': typ,
                'probNum': pid,
            },
        ).json()
        return str(data['runId'])

    def get_submission(self, id):
        r = self.session.post('https://vjudge.net/solution/data/%s' % id).json()
        if r['statusType'] == 2:
            return
        v = (
            Verdict.ACCEPTED
            if r.get('statusType') == 0
            else self.VERD.get(r.get('statusCanonical'), Verdict.OTHER_FAIL)
        )
        data = {}
        if r.get('additionalInfo'):
            data['info'] = r['additionalInfo']
        if r.get('codeImgUrl'):
            data['codeImg'] = 'https://vjudge.net' + r['codeImgUrl']
        return Submission(
            id,
            v,
            r['oj'] + '-' + r['probNum'],
            0 if v.value & 255 else 100,
            r.get('code'),
            r.get('runtime'),
            r.get('memory'),
            data=data or None,
        )
