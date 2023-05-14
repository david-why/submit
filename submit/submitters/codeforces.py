import re
import warnings

from bs4 import BeautifulSoup

from ..base import Case, Language, Problem, Submission, SubmitterBase, TextType, Verdict

__all__ = ['CodeforcesSubmitter']


class CodeforcesSubmitter(SubmitterBase):
    name = 'codeforces'
    LANG = {Language.C__: '54', Language.PYTHON3: '70'}

    PSET_RE = re.compile(
        'https?://codeforces.com/problemset/problem/([0-9]+)/([A-Z0-9]+)'
    )
    ACMSGURU_RE = re.compile(
        'https?://codeforces.com/problemsets/(acmsguru)/problem/99999/([0-9]+)'
    )
    COMP_RE = re.compile('https?://codeforces.com/contest/([0-9]+)/problem/([A-Z0-9]+)')

    def __init__(self):
        super().__init__()
        r = self.session.get('https://codeforces.com')
        if 'Redirecting...' in r.text:
            try:
                from Crypto.Cipher import AES
            except ModuleNotFoundError as e:
                raise ImportError('Please install PyCryptodome!') from e

            def toNumbers(s):
                b = []
                for i in range(0, len(s), 2):
                    b.append(int(s[i : i + 2], 16))
                return bytes(b)

            a = r.text.index('a=toNumbers')
            a = r.text[r.text.index('"', a) + 1 :]
            a = toNumbers(a[: a.index('"')])
            b = r.text.index('b=toNumbers')
            b = r.text[r.text.index('"', b) + 1 :]
            b = toNumbers(b[: b.index('"')])
            c = r.text.index('c=toNumbers')
            c = r.text[r.text.index('"', c) + 1 :]
            c = toNumbers(c[: c.index('"')])
            cr = AES.new(a, mode=AES.MODE_CBC, IV=b)
            self.session.cookies.set('RCPC', cr.decrypt(c).hex())

    @classmethod
    def parse_problem_url(cls, url):
        match = (
            cls.PSET_RE.match(url)
            or cls.COMP_RE.match(url)
            or cls.ACMSGURU_RE.match(url)
        )
        if not match:
            return
        return '%s_%s' % match.groups()

    @classmethod
    def get_problem_url(cls, id):
        try:
            contest, problem = id.split('_')
        except:
            return
        if contest == 'acmsguru':
            return (
                'https://codeforces.com/problemsets/acmsguru/problem/99999/%s' % problem
            )
        return 'https://codeforces.com/contest/%s/problem/%s' % (contest, problem)

    @classmethod
    def search_problem(cls, text):
        match = (
            cls.PSET_RE.search(text)
            or cls.COMP_RE.search(text)
            or cls.ACMSGURU_RE.search(text)
        )
        if not match:
            return
        return '%s_%s' % match.groups()

    def _csrf(self, url):
        text = self.session.get(url).text
        i = text.index('csrf=') + 6
        return text[i : text.index("'", i)]

    def login(self, username, password):
        csrf = self._csrf('https://codeforces.com/enter')
        r = self.session.post(
            'https://codeforces.com/enter',
            data={
                'csrf_token': csrf,
                'action': 'enter',
                'ftaa': 'n/a',
                'bfaa': 'n/a',
                'handleOrEmail': username,
                'password': password,
                '_tta': '176',
                'remember': 'on',
            },
        )
        return 'enter' not in r.url

    def logout(
        self,
        __re=re.compile(
            r'Codeforces.showMessage\("Goodbye, .*. '
            r'Looking forward to seeing you at Codeforces."\);'
        ),
    ):
        r = self.session.get('https://codeforces.com')
        if '/logout' not in r.text:
            return False
        i = r.text.index('/logout')
        r = self.session.get(
            'https://codeforces.com'
            + r.text[r.text.rindex('"', 0, i) + 1 : i]
            + '/logout'
        )
        return __re.search(r.text)

    @property
    def logged_in(self):
        r = self.session.get('https://codeforces.com/profile')
        return r.url.startswith('https://codeforces.com/profile/')

    def get_problem(self, id):
        u = self.get_problem_url(id)
        if u is None:
            return
        prob = self.session.get(u)
        return Problem(
            id,
            str(
                BeautifulSoup(prob.content, 'html.parser').select_one(
                    '.problem-statement'
                )
            ).strip(),
            TextType.HTML,
        )

    def submit(self, id, code, lang=Language.C__):
        contest, problem = id.split('_')
        if contest == 'acmsguru':
            url = 'https://codeforces.com/contest/acmsguru/submit'
            data = {'submittedProblemIndex': problem}
        else:
            url = 'https://codeforces.com/problemsets/%s/submit' % contest
            data = {'submittedProblemCode': problem}
        csrf = self._csrf(url)
        data.update(
            {
                'csrf_token': csrf,
                'ftaa': 'n/a',
                'bfaa': 'n/a',
                'action': 'submitSolutionFormSubmitted',
                'programTypeId': self.LANG[lang],
                'source': code,
                'tabSize': '4',
            }
        )
        r = self.session.post(url, params={'csrf_token': csrf}, data=data)
        i = r.text.index('submission-id="') + 15
        return '%s_%s_%s' % (contest, problem, r.text[i : r.text.index('"', i)])

    @staticmethod
    def _parse_verdict(text):
        if 'verdict-accepted' in text:
            return Verdict.ACCEPTED
        elif 'verdict-rejected' in text:
            if 'Time limit exceeded' in text:
                return Verdict.TIME_LIMIT_EXCEEDED
            elif 'Wrong answer' in text:
                return Verdict.WRONG_ANSWER
            elif 'Runtime error' in text:
                return Verdict.RUNTIME_ERROR
            elif 'Idleness limit exceeded' in text:
                return Verdict.IDLENESS_LIMIT_EXCEEDED
        warnings.warn(RuntimeWarning('Unknown verdict: %r' % text))
        return Verdict.UNKNOWN

    def get_submission(self, id):
        contest, pp, sid = id.split('_')
        csrf = self._csrf('https://codeforces.com')
        r = self.session.post(
            'https://codeforces.com/data/submitSource',
            data={'submissionId': sid, 'csrf_token': csrf},
        )
        try:
            data = r.json()
        except:
            return
        if data.get('waiting', 'true') == 'true':
            return
        pid = '%s_%s' % (contest, pp)
        code = data.get('source') or None
        if data.get('compilationError') == 'true':
            return Submission(id, Verdict.COMPILATION_ERROR, pid, 0, code)
        mtim = 0
        mmem = 0
        verd = Verdict.ACCEPTED
        if 'testCount' not in data:
            n = 0
        else:
            n = int(data['testCount'])
            verd = self._parse_verdict(data.get('verdict'))
        cases = []
        for i in range(n):
            try:
                v = Verdict(data.get('verdict#%d' % (i + 1)))
            except:
                v = None
            time = int(data['timeConsumed#%d' % (i + 1)])
            mem = int(data['memoryConsumed#%d' % (i + 1)]) // 1024
            cases.append(
                Case(
                    time,
                    mem,
                    data.get('input#%d' % (i + 1)),
                    data.get('output#%d' % (i + 1)),
                    data.get('answer#%d' % (i + 1)),
                    v,
                    data.get('checkerStdoutAndStderr#%d' % (i + 1)),
                )
            )
            mtim = max(mtim, time)
            mmem = max(mmem, mem)
        return Submission(
            id,
            verd,
            pid,
            100 if verd == Verdict.ACCEPTED else 0,
            code,
            mtim,
            mmem,
            cases,
        )
