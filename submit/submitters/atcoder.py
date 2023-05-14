import re

from bs4 import BeautifulSoup, Tag

from ..base import Case, Language, Problem, Submission, SubmitterBase, TextType, Verdict

__all__ = ['AtCoderSubmitter']


class AtCoderSubmitter(SubmitterBase):
    name = 'atcoder'
    LANG = {Language.C__: '4003', Language.PYTHON3: '4047'}

    RE = re.compile(
        'https:?//atcoder.jp/contests/([0-9a-zA-Z_]+)/tasks/([0-9a-zA-Z_]+)'
    )

    def __init__(self):
        super().__init__()
        self.session.cookies.set('language', 'en', domain='.atcoder.jp')

    @classmethod
    def parse_problem_url(cls, url):
        match = cls.RE.match(url)
        if not match:
            return
        return '%s/%s' % match.groups()

    @classmethod
    def get_problem_url(cls, id):
        try:
            contest, problem = id.split('/')
        except:
            try:
                contest, prob = id.split('_')
                problem = '%s_%s' % (contest, prob)
            except:
                return
        return 'https://atcoder.jp/contests/%s/tasks/%s' % (contest, problem)

    @classmethod
    def search_problem(cls, text):
        match = cls.RE.search(text)
        if not match:
            return
        return '%s/%s' % match.groups()

    def _csrf(self, url):
        r = self.session.get(url).text
        r = r[r.index('csrfToken = "') + 13 :]
        r = r[: r.index('"')]
        return r

    def login(self, username, password):
        c = self._csrf('https://atcoder.jp/login')
        r = self.session.post(
            'https://atcoder.jp/login',
            data={'username': username, 'password': password, 'csrf_token': c},
        )
        return 'login' not in r.url

    def logout(self):
        c = self._csrf('https://atcoder.jp/home')
        self.session.post('https://atcoder.jp/logout', data={'csrf_token': c})
        return not self.logged_in

    @property
    def logged_in(self):
        r = self.session.get('https://atcoder.jp/settings')
        return r.url.startswith('https://atcoder.jp/settings')

    def get_problem(self, id):
        u = self.get_problem_url(id)
        if u is None:
            return
        r = self.session.get(u)
        s = BeautifulSoup(r.content, 'html.parser')
        ps = s.select('#task-statement .lang-en .part')
        t = ''
        ipt, opt = [], []
        for p in ps:
            t += str(p)
            h3 = p.select_one('h3')
            if h3 is not None:
                x = h3.text.strip()
                if x.startswith('Sample Input '):
                    ipt.append(p.select_one('pre').text.replace('\r\n', '\n'))
                elif x.startswith('Sample Output '):
                    opt.append(p.select_one('pre').text.replace('\r\n', '\n'))
        return Problem(id, t, TextType.HTML, list(zip(ipt, opt)) or None)

    def submit(self, id, code, lang):
        _, contest, problem = id.split('/')
        c = self._csrf(
            'https://atcoder.jp/contests/%s/submit?taskScreenName=%s'
            % (contest, problem)
        )
        r = self.session.post(
            'https://atcoder.jp/contests/%s/submit' % contest,
            data={
                'data.TaskScreenName': problem,
                'data.LanguageId': self.LANG[lang],
                'sourceCode': code,
                'csrf_token': c,
            },
        )
        s = BeautifulSoup(r.content, 'html.parser')
        sid = s.select_one('.table-responsive td.submission-score').attrs.get('data-id')
        return '%s/%s' % (contest, sid)

    def _parse_verd(self, verd):
        if verd == 'CE':
            ve = Verdict.COMPILATION_ERROR
        elif verd in {'MLE', 'RE', 'OLE', 'IE'}:
            ve = Verdict.RUNTIME_ERROR
        elif verd == 'TLE':
            ve = Verdict.TIME_LIMIT_EXCEEDED
        elif verd == 'WA':
            ve = Verdict.WRONG_ANSWER
        elif verd == 'AC':
            ve = Verdict.ACCEPTED
        else:
            ve = Verdict.UNKNOWN
        return ve

    def get_submission(self, id):
        contest, sid = id.split('/')
        r = self.session.get(
            'https://atcoder.jp/contests/%s/submissions/%s' % (contest, sid)
        )
        s = BeautifulSoup(r.content, 'html.parser')
        sta = s.select_one('#judge-status span')
        if sta is None:
            raise ValueError(s.text)
        stat = sta.text
        if stat == 'WJ' or '/' in stat:
            return
        ve = self._parse_verd(stat)
        msg = sta.attrs.get('title')
        code = s.select_one('#submission-code')
        if code:
            code = code.text
        dettab = sta.parent.parent.parent
        tds = dettab.select('td')
        prob = self.parse_problem_url(tds[1].select_one('a').attrs.get('href') or '')
        sco = int(tds[4].text)
        tim = int(''.join(filter(lambda x: x.isdigit(), tds[7].text)))
        siz = int(''.join(filter(lambda x: x.isdigit(), tds[8].text)))
        v = dettab.parent.next_siblings
        cases = []
        for t in v:
            if (
                not isinstance(t, Tag)
                or t.select_one('th') is None
                or t.select_one('th').text.strip() != 'Case Name'
            ):
                continue
            cs = t.select('tr')[1:]
            for c in cs:
                tds = c.select('td')
                cases.append(
                    Case(
                        int(''.join(filter(lambda x: x.isdigit(), tds[2].text))),
                        int(''.join(filter(lambda x: x.isdigit(), tds[3].text))),
                        verdict=self._parse_verd(c.select_one('span').text.strip()),
                    )
                )
        return Submission(id, ve, prob, sco, code, tim, siz, cases, msg)
