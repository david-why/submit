import urllib.parse

from bs4 import BeautifulSoup

from ..base import Case, Language, Problem, Submission, SubmitterBase, TextType, Verdict

__all__ = ['USACOTrainingSubmitter']


class USACOContestSubmitter(SubmitterBase):
    name = 'usaco_contest'
    LANG = {Language.C__: '7', Language.PYTHON3: '4'}

    @classmethod
    def parse_problem_url(cls, url):
        pr = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(pr.query)
        if (
            pr.netloc == 'www.usaco.org'
            and pr.path == '/index.php'
            and qs['page'] == ['viewproblem2']
            and 'cpid' in qs
        ):
            return qs['cpid'][0]

    @classmethod
    def get_problem_url(cls, id):
        return 'http://www.usaco.org/index.php?page=viewproblem2&cpid=%s' % id

    @classmethod
    def search_problem(cls, text):
        if 'cpid=' not in text:
            return
        i = text.index('cpid=') + 5
        s = ''
        while text[i].isdigit():
            s += text[i]
            i += 1
        return s

    def login(self, username, password):
        return (
            self.session.post(
                'http://www.usaco.org/current/tpcm/login-session.php',
                data={'uname': username, 'password': password},
            ).json()['code']
            == 1
        )

    def logout(self):
        return self.session.get(
            'http://www.usaco.org/current/tpcm/logout.php'
        ).url.endswith('index.php')

    @property
    def logged_in(self):
        return 'Welcome, ' in self.session.get('http://www.usaco.org/index.php').text

    def get_problem(self, id: str):
        u = self.get_problem_url(id)
        if u is None:
            return
        r = self.session.get(u)
        s = BeautifulSoup(r.text, 'html.parser')
        title = ' '.join(x.text for x in s.select('h2')).strip()
        desc = s.select_one('.problem-text')
        cases = []
        for i, o in zip(s.select('pre.in'), s.select('pre.out')):
            cases.append((i.text.strip(), o.text.strip()))
        return Problem(id, title + '\n' + desc.text, TextType.TEXT, cases)

    def submit(self, id, code, lang):
        self.session.post(
            'http://www.usaco.org/current/tpcm/submit-solution.php',
            files={
                'cpid': (None, id),
                'language': (None, self.LANG[lang]),
                'sourcefile': ('file', code.encode()),
            },
        )
        r = self.session.get(self.get_problem_url(id))
        s = BeautifulSoup(r.content, 'html.parser').select_one('#last-status')
        if s is None:
            return
        return '%s_%s' % (id, s.attrs.get('data-sid'))

    @staticmethod
    def _parse_mem(mem):
        mem = mem.lower()
        if mem.endswith('gb'):
            return float(mem[:-2]) * 1024 * 1024
        if mem.endswith('mb'):
            return float(mem[:-2]) * 1024
        if mem.endswith('kb'):
            return float(mem[:-2])

    @staticmethod
    def _parse_time(tim):
        tim = tim.lower()
        if tim.endswith('ms'):
            return float(tim[:-2])
        if tim.endswith('s'):
            return float(tim[:-2]) * 1000

    def get_submission(self, id):
        pid, _, id = id.partition('_')
        r = self.session.post(
            'http://www.usaco.org/current/tpcm/status-update.php', data={'sid': id}
        ).json()
        if int(r['cd']) <= -8:
            return
        if r['sr'].startswith('Compilation Error'):
            return Submission(id, Verdict.COMPILATION_ERROR, pid, 0, data=r['output'])
        if r['sr'].startswith('Incorrect answer on sample input case'):
            return Submission(id, Verdict.WRONG_ANSWER, pid, 0, data=r['output'])
        if not r['sr'].startswith('Submitted;'):
            raise ValueError(r)
        s = BeautifulSoup(r['jd'], 'html.parser')
        cases = []
        ok = 0
        tim = mem = 0.0
        verd = Verdict.ACCEPTED
        for c in s.select('a'):
            print(c)
            if c.attrs.get('title') == 'Correct answer':
                ms, ts = c.select('.info>span')
                m = self._parse_mem(ms.text)
                t = self._parse_time(ts.text)
                tim = max(t, tim)
                mem = max(m, mem)
                cases.append(Case(t, m, verdict=Verdict.ACCEPTED))
                ok += 1
            elif c.attrs.get('title') == 'Time limit exceeded':
                cases.append(Case(0, 0, verdict=Verdict.TIME_LIMIT_EXCEEDED))
                verd = verd if verd != Verdict.ACCEPTED else Verdict.TIME_LIMIT_EXCEEDED
            elif c.attrs.get('title') == 'Wrong answer':
                cases.append(Case(0, 0, verdict=Verdict.WRONG_ANSWER))
                verd = verd if verd != Verdict.ACCEPTED else Verdict.WRONG_ANSWER
            elif c.attrs.get('title').startswith('Runtime error'):
                cases.append(Case(0, 0, verdict=Verdict.RUNTIME_ERROR))
                verd = verd if verd != Verdict.ACCEPTED else Verdict.RUNTIME_ERROR
            else:
                raise ValueError(c)
        return Submission(
            id,
            verd,
            pid,
            100 if ok == len(cases) else 0,
            time=tim,
            memory=mem,
            cases=cases,
            data={'code': int(r['cd'])},
        )
