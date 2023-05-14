import re

from bs4 import BeautifulSoup, NavigableString, Tag

from ..base import Case, Language, Problem, Submission, SubmitterBase, TextType, Verdict

__all__ = ['CSESSubmitter']


class CSESSubmitter(SubmitterBase):
    name = 'cses'
    RE = re.compile('https?://cses.fi/problemset/task/([0-9]+)/?')
    PATH_RE = re.compile('/problemset/task/([0-9]+)/?')
    RES_RE = re.compile('https?://cses.fi/problemset/result/([0-9]+)/?')
    LANG = {Language.C__: ('C++', 'C++17'), Language.PYTHON3: ('Python3', 'PyPy3')}
    VERD = {
        'ACCEPTED': Verdict.ACCEPTED,
        'WRONG ANSWER': Verdict.WRONG_ANSWER,
        'RUNTIME ERROR': Verdict.RUNTIME_ERROR,
        'TIME LIMIT EXCEEDED': Verdict.TIME_LIMIT_EXCEEDED,
    }

    @classmethod
    def parse_problem_url(cls, url):
        match = cls.RE.match(url)
        if match:
            return match.group(1)

    @classmethod
    def get_problem_url(cls, id):
        return 'https://cses.fi/problemset/task/' + id

    @classmethod
    def search_problem(cls, text):
        match = cls.RE.search(text)
        if match:
            return match.group(1)

    def login(self, username, password):
        r = self.session.get('https://cses.fi/login')
        csrf = (
            BeautifulSoup(r.content, 'html.parser')
            .select_one('input[name="csrf_token"]')
            .attrs['value']
        )
        login = self.session.post(
            'https://cses.fi/login',
            data={'csrf_token': csrf, 'nick': username, 'pass': password},
        )
        return not login.url.endswith('login')

    def logout(self):
        return self.session.get('https://cses.fi/logout').status_code < 400

    @property
    def logged_in(self):
        r = self.session.get('https://cses.fi/')
        return not (
            BeautifulSoup(r.content, 'html.parser')
            .select_one('.controls a.account')
            .attrs['href']
        ).endswith('/login')

    def get_problem(self, id):
        r = self.session.get(self.get_problem_url(id))
        soup = BeautifulSoup(r.content, 'html.parser')
        content = soup.select_one('div.content')
        if not content:
            return
        return Problem(id, content.text, TextType.TEXT)

    def submit(self, id, code, lang):
        sel, opt = self.LANG[lang]
        r = self.session.get('https://cses.fi/problemset/submit/%s/' % id)
        csrf = (
            BeautifulSoup(r.content, 'html.parser')
            .select_one('input[name="csrf_token"]')
            .attrs['value']
        )
        data = {
            'csrf_token': csrf,
            'task': id,
            'lang': sel,
            'type': 'course',
            'target': 'problemset',
        }
        if opt is not None:
            data['option'] = opt
        files = {k: (None, v) for k, v in data.items()}
        files['file'] = ('file', code.encode())
        submit = self.session.post('https://cses.fi/course/send.php', files=files)
        match = self.RES_RE.match(submit.url)
        if match:
            return match.group(1)

    def get_submission(self, id):
        r = self.session.get(
            'https://cses.fi/ajax/get_status.php', params={'entry': id}
        )
        if r.status_code >= 400 or r.text.startswith(('TESTING', 'PENDING')):
            return
        r = self.session.get('https://cses.fi/problemset/result/%s/' % id)
        soup = BeautifulSoup(r.content, 'html.parser')
        vertext = soup.select_one('.inline-score.verdict').text
        verdict = self.VERD.get(vertext, Verdict.UNKNOWN)
        problem = self.PATH_RE.match(
            soup.select_one('.summary-table a').attrs['href']
        ).group(1)
        code = soup.select_one('pre.prettyprint').text
        tim = 0.0
        caseio = {}
        for div in soup.select('div.closeable'):
            h3 = div.select_one('h3.caption')
            if not h3 or h3.text != 'Test details':
                continue
            div = div.select_one('div')
            err = False
            for el in div:
                if isinstance(el, Tag) and el.name.lower() == 'br':
                    continue
                if err:
                    case['message'] = el.text
                    err = False
                if isinstance(el, NavigableString):
                    if el.text == 'Error:':
                        err = True
                if not isinstance(el, Tag) or el.name.lower() == 'br':
                    continue
                if el.name.lower() == 'h4':
                    case = caseio.setdefault(el.attrs['id'], {})
                elif el.name.lower() == 'table':
                    th = el.select_one('tbody th')
                    td = el.select_one('tbody td')
                    if not (th and td):
                        continue
                    samp = td.select_one('samp') or td
                    text = samp.text
                    actions = td.select_one('.samp-actions')
                    if text.endswith('...') and actions:
                        view = actions.select_one('a.view')
                        text += ' (https://cses.fi%s)' % view.attrs['href']
                    if th.text == 'input':
                        case['input'] = text
                    elif th.text == 'correct output':
                        case['answer'] = text
                    elif th.text == 'user output':
                        case['output'] = text
            break
        cases = []
        for tr in soup.select('table.closeable tr'):
            if tr.select_one('th'):
                continue
            td = tr.select('td')
            vertext = td[1].text
            ctim = float(td[2].text[:-2]) * 1000
            tim = max(tim, ctim)
            cid = td[3].select_one('a').attrs['href'].strip('#')
            case = caseio.get(cid, {})
            cases.append(
                Case(ctim, 0, verdict=self.VERD.get(vertext, Verdict.UNKNOWN), **case)
            )
        return Submission(
            id,
            verdict,
            problem,
            100 if verdict == Verdict.ACCEPTED else 0,
            code,
            tim,
            cases=cases,
        )
