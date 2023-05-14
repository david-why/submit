import re
import urllib.parse

from bs4 import BeautifulSoup

from ..base import Problem, Submission, SubmitterBase, TextType, Verdict

__all__ = ['USACOTrainingSubmitter']


class USACOTrainingSubmitter(SubmitterBase):
    name = 'usaco'

    TASK_RE = re.compile(r'TASK: (\S+)')

    def __init__(self):
        super().__init__()
        self._a = None

    def __getstate__(self):
        return (super().__getstate__(), self._a)

    def __setstate__(self, state):
        ss, self._a = state
        super().__setstate__(ss)

    @classmethod
    def parse_problem_url(cls, url):
        pr = urllib.parse.urlparse(url)
        if pr.netloc != 'train.usaco.org' or pr.path != '/usacoprob2':
            return
        q = urllib.parse.parse_qs(pr.query)
        if 'S' in q:
            return q['S'][0]

    @classmethod
    def get_problem_url(cls, id):
        return 'https://train.usaco.org/usacoprob2?S=%s' % id

    @classmethod
    def search_problem(cls, text):
        match = cls.TASK_RE.search(text)
        if match:
            return match.group(1)

    def login(self, username, password):
        r = self.session.post(
            'https://train.usaco.org',
            data={
                'NAME': username,
                'PASSWORD': password,
                'SUBMIT': 'ENTER',
            },
        )
        a = r.text.index('?a=') + 3
        self._a = r.text[a : r.text.index('"', a)]
        return True

    def logout(self):
        self.session.post('https://train.usaco.org/usacologout', params={'a': self._a})
        self._a = None
        return True

    @property
    def logged_in(self):
        if not self._a:
            return False
        r = self.session.get('https://train.usaco.org/', params={'a': self._a})
        return 'Refresh this page' in r.text

    def get_problem(self, id):
        r = self.session.get(
            'https://train.usaco.org/usacoprob2', params={'a': self._a, 'S': id}
        )
        return Problem(
            id,
            r.text[
                r.text.index(' width=742 height=118>')
                + 23 : r.text.index('<div style=\'width:6.25in')
            ].strip(),
            TextType.HTML,
            [
                tuple(
                    map(
                        lambda x: x.text.strip(),
                        BeautifulSoup(r.content, 'html.parser').select('pre')[-2:],
                    )
                )
            ],
        )

    def submit(self, id, code, lang):
        lang  # type: ignore
        r = self.session.post(
            'https://train.usaco.org/upload3',
            files={
                'filename': ('file', code.encode()),
                'a': (None, self._a),
                'S': (None, id),
            },
        )
        return (
            id
            + '/'
            + BeautifulSoup(r.content, 'html.parser').select_one('div>font>div').text
        )

    def get_submission(self, id):
        pid, _, id = id.partition('/')
        if 'Compile: OK' not in id:
            return Submission(
                pid,
                Verdict.COMPILATION_ERROR,
                pid,
                0,
                data=id[
                    id.index('did not compile correctly:')
                    + 26 : id.index('Compile errors;')
                ].strip(),
            )
        i = 1
        time = 0
        memory = 0
        while 'Test %d: ' % i in id:
            p = id.index(' KB', id.index('Test %d: ' % i)) - 1
            while id[p] not in '[(, ':
                p -= 1
            memory = max(memory, float(id[p + 1 : id.index(' KB', p)]))
            if id[p] in '[(':
                if 'Test %d: RUNTIME' % i not in id:
                    raise ValueError(id)
                timei = id.index('Test %d: RUNTIME' % i)
                time = id[timei + len('%d: RUNTIME' % i) : id.index('>', timei)]
                return Submission(
                    pid,
                    Verdict.TIME_LIMIT_EXCEEDED,
                    pid,
                    0,
                    time=float(time),
                    memory=memory,
                    data={
                        'message': id[
                            id.index('> Run %d' % i) : id.index('Full Test Data')
                        ]
                        .strip()
                        .replace('-' * 19 + '    ', '-' * 19 + '\n        '),
                        'inurl': 'https://train.usaco.org/usacodatashow?a=%s' % self._a,
                        'outurl': 'https://train.usaco.org/usacodatashow?a=%s&i=out'
                        % self._a,
                    },
                )
            while id[p] not in '[(':
                p -= 1
            time = int(max(time, float(id[p + 1 : id.index(' ', p)]) * 1000))
            i += 1
        i -= 1
        if 'All tests OK.' in id:
            i = id.index('All tests OK.') + 14
            return Submission(pid, Verdict.ACCEPTED, pid, 100, time=time, memory=memory)
        if 'Test %d: BADCHECK' % i in id or 'Test %d: NOOUTPUT' % i in id:
            return Submission(
                pid,
                Verdict.WRONG_ANSWER,
                pid,
                0,
                time=time,
                memory=memory,
                data={
                    'message': id[id.index('> Run %d' % i) : id.index('Full Test Data')]
                    .strip()
                    .replace('-' * 19 + '    ', '-' * 19 + '\n        '),
                    'inurl': 'https://train.usaco.org/usacodatashow?a=%s' % self._a,
                    'outurl': 'https://train.usaco.org/usacodatashow?a=%s&i=out'
                    % self._a,
                },
            )
        raise ValueError(id)

    def dump(self):
        return {'a': self._a, 'super': super().dump()}

    def load(self, data):
        self._a = data['a']
        super().load(data['super'])
