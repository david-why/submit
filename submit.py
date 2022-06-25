#!/usr/bin/env python3
import argparse
import getpass
import json
import os
import pickle
import random
import re
import string
import tempfile
import time
import urllib.parse
import warnings
from abc import ABC, abstractmethod
from enum import IntEnum
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

CONFIG_DIR = Path('~/.submitter').expanduser()  # type: Path


def get_pass():
    return input('Username: '), getpass.getpass()


def _load_or_get(obj):
    obj.session = requests.Session()
    name = obj.NAME
    if not CONFIG_DIR.is_dir():
        CONFIG_DIR.mkdir()
    cfgdir = CONFIG_DIR / name  # type: Path
    if not cfgdir.is_dir():
        cfgdir.mkdir()
    sess = cfgdir / 'session'
    if sess.is_file():
        obj.session = pickle.load(sess.open('rb'))
    else:
        un = None
        pwd = None
        if (cfgdir / 'username').is_file():
            with (cfgdir / 'username').open() as f:
                un = f.read()
        if (cfgdir / 'password').is_file():
            with (cfgdir / 'password').open() as f:
                pwd = f.read()
        if un is None or pwd is None:
            un, pwd = get_pass()
            save = input('Save username & password (Y/n)? ')
            save = save == '' or save.startswith(('y', 'Y'))
            if save:
                with (cfgdir / 'username').open('w') as f:
                    f.write(un)
                (cfgdir / 'username').chmod(0o600)
                with (cfgdir / 'password').open('w') as f:
                    f.write(pwd)
                (cfgdir / 'password').chmod(0o600)
        obj.username = un
        obj.password = pwd
        obj.session = requests.Session()
        obj.login()
        _save_sess(obj)
    if not obj.logged_in:
        obj.logout()
        _load_or_get(obj)


def _save_sess(obj):
    pickle.dump(obj.session, (CONFIG_DIR / obj.NAME / 'session').open('wb'))


class Submission:
    class Status(IntEnum):
        ACCEPTED = 0
        WRONG_ANSWER = 1
        TIME_LIMIT_EXCEEDED = 2
        RUNTIME_ERROR = 3
        COMPILATION_ERROR = 4
        IDLENESS_LIMIT_EXCEEDED = 5

    ACCEPTED = Status.ACCEPTED
    WRONG_ANSWER = Status.WRONG_ANSWER
    TIME_LIMIT_EXCEEDED = Status.TIME_LIMIT_EXCEEDED
    RUNTIME_ERROR = Status.RUNTIME_ERROR
    COMPILATION_ERROR = Status.COMPILATION_ERROR
    IDLENESS_LIMIT_EXCEEDED = Status.IDLENESS_LIMIT_EXCEEDED

    def __init__(
        self,
        status,
        message,
        score,
        time=None,
        memory=None,
        wrong=None,
        data=None,
    ):
        self.status = self.Status(status)
        self.message = message
        self.score = score
        self.time = time
        self.memory = memory
        self.wrong = wrong
        self.data = data

    def to_dict(self):
        return {
            'status': int(self.status),
            'message': self.message,
            'score': self.score,
            'time': self.time,
            'memory': self.memory,
            'wrong': self.wrong,
            'data': self.data,
        }

    def to_json(self):
        return json.dumps(self.to_dict(), separators=(',', ':'))

    @classmethod
    def from_dict(cls, data):
        self = cls.__new__(cls)  # type: Submission
        self.status = self.Status(data['status'])
        self.message = data['message']
        self.score = data['score']
        self.time = data['time']
        self.memory = data['memory']
        self.wrong = data['wrong']
        self.data = data['data']
        return self

    @classmethod
    def from_json(cls, js):
        return cls.from_dict(json.loads(js))


class Submitter(ABC):
    NAME: str
    LANG: dict

    username: str
    password: str
    session: requests.Session

    __init__ = _load_or_get

    @classmethod
    @abstractmethod
    def _parse(cls, url):
        ...

    @classmethod
    @abstractmethod
    def _unparse(cls, id):
        ...

    @abstractmethod
    def login(self):
        ...

    @property
    @abstractmethod
    def logged_in(self):
        ...

    def logout(self):
        self.session = requests.Session()
        sess = CONFIG_DIR / self.NAME / 'session'
        sess.unlink(True)

    @abstractmethod
    def submit(self, id, file, lang='c++'):
        ...

    def submit_file(self, id, filename, lang='c++'):
        return self.submit(id, open(filename), lang)

    @abstractmethod
    def wait_submission(self, id):
        ...


class CodeforcesSubmitter(Submitter):
    """Submit to Codeforces."""

    NAME = 'codeforces'
    LANG = {'c++': '54'}

    PSET_RE = re.compile(
        'https?://codeforces.com/problemset/problem/([0-9]+)/([A-Z0-9]+)'
    )
    COMP_RE = re.compile(
        'https?://codeforces.com/contest/([0-9]+)/problem/([A-Z0-9]+)'
    )

    def __init__(self):
        super().__init__()
        r = self.session.get('https://codeforces.com')
        if 'Redirecting...' in r.text:
            try:
                from Crypto.Cipher import AES
            except ModuleNotFoundError as e:
                raise ImportError('Did you install PyCrypto?') from e

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
        if not self.logged_in:
            self.logout()
            _load_or_get(self)

    @staticmethod
    def _ftaa():
        return ''.join(random.choices(string.ascii_letters, k=18))

    @staticmethod
    def _bfaa():
        return 'f1b3f18c715565b589b7823cda7448ce'

    @classmethod
    def _parse(cls, url):
        match = cls.PSET_RE.match(url) or cls.COMP_RE.match(url)
        if not match:
            return
        return 'CF_%s_%s' % match.groups()

    @classmethod
    def _unparse(cls, id):
        try:
            CF, contest, problem = id.split('_')
        except:
            return
        if CF != 'CF':
            return
        return 'https://codeforces.com/contest/%s/problem/%s' % (
            contest,
            problem,
        )

    def _csrf(self, url):
        text = self.session.get(url).text
        i = text.index('csrf=') + 6
        return text[i : text.index("'", i)]

    def login(self):
        csrf = self._csrf('https://codeforces.com/enter')
        self.session.post(
            'https://codeforces.com/enter',
            data={
                'csrf_token': csrf,
                'action': 'enter',
                'ftaa': self._ftaa(),
                'bfaa': self._bfaa(),
                'handleOrEmail': self.username,
                'password': self.password,
                '_tta': '176',
                'remember': 'on',
            },
        )

    @property
    def logged_in(self):
        r = self.session.get('https://codeforces.com/profile')
        return r.url.startswith('https://codeforces.com/profile/')

    def submit(self, id, file, lang='c++'):
        _, contest, problem = id.split('_')
        url = 'https://codeforces.com/contest/%s/submit' % contest
        csrf = self._csrf(url)
        r = self.session.post(
            url,
            params={'csrf_token': csrf},
            data={
                'csrf_token': csrf,
                'ftaa': self._ftaa(),
                'bfaa': self._bfaa(),
                'action': 'submitSolutionFormSubmitted',
                'submittedProblemIndex': problem,
                'programTypeId': self.LANG[lang],
                'source': file.read(),
                'tabSize': 4,
            },
        )
        i = r.text.index('submission-id="') + 15
        return '%s_%s' % (contest, r.text[i : r.text.index('"', i)])

    def wait_submission(self, id):
        url = 'https://codeforces.com/contest/%s/submission/%s' % tuple(
            id.split('_')
        )
        while True:
            r = requests.get(url)
            s = BeautifulSoup(r.content, 'html.parser')
            data = (
                s.select_one('.datatable table').select('tr')[1].select('td')
            )
            verd_div = data[4]
            verd = verd_div.select_one('span')
            if verd is None:
                if 'Compilation error' in verd_div.text:
                    return Submission(
                        Submission.COMPILATION_ERROR,
                        verd_div.text.strip(),
                        0,
                        wrong=-1,
                    )
            msg = verd.text
            classes = verd.attrs['class']
            if 'verdict-waiting' in classes:
                time.sleep(1)
                continue
            if 'verdict-accepted' in classes:
                return Submission(
                    Submission.ACCEPTED,
                    msg,
                    100,
                    int(data[5].text.strip()[:-3]),
                    int(data[6].text.strip()[:-3]),
                )
            elif 'verdict-rejected' in classes:
                if 'Time limit exceeded' in msg:
                    st = Submission.TIME_LIMIT_EXCEEDED
                elif 'Wrong answer' in msg:
                    st = Submission.WRONG_ANSWER
                elif 'Runtime error' in msg:
                    st = Submission.RUNTIME_ERROR
                elif 'Idleness limit exceeded' in msg:
                    st = Submission.IDLENESS_LIMIT_EXCEEDED
                else:
                    warnings.warn(
                        RuntimeWarning(
                            'Unknown status: %r, using RUNTIME_ERROR' % msg
                        )
                    )
                return Submission(
                    st,
                    msg,
                    0,
                    int(data[5].text.strip()[:-3]),
                    int(data[6].text.strip()[:-3]),
                    int(verd.select_one('span').text),
                )


class AtCoderSubmitter(Submitter):
    """Submit to AtCoder."""

    NAME = 'atcoder'
    LANG = {'c++': '4003'}

    RE = re.compile(
        'https:?//atcoder.jp/contests/([0-9a-zA-Z_]+)/tasks/([0-9a-zA-Z_]+)'
    )

    def __init__(self):
        super().__init__()
        if not self.logged_in:
            self.logout()
            _load_or_get(self)

    @classmethod
    def _parse(cls, url):
        match = cls.RE.match(url)
        if not match:
            return
        return 'AT/%s/%s' % match.groups()

    @classmethod
    def _unparse(cls, id):
        try:
            AT, contest, problem = id.split('/')
            assert AT == 'AT'
        except:
            return
        return 'https://atcoder.jp/contests/%s/tasks/%s' % (contest, problem)

    def _csrf(self, url):
        r = self.session.get(url).text
        r = r[r.index('csrfToken = "') + 13 :]
        r = r[: r.index('"')]
        return r

    def login(self):
        c = self._csrf('https://atcoder.jp/login')
        self.session.post(
            'https://atcoder.jp/login',
            data={
                'username': self.username,
                'password': self.password,
                'csrf_token': c,
            },
        )

    @property
    def logged_in(self):
        r = self.session.get('https://atcoder.jp/settings')
        return r.url.startswith('https://atcoder.jp/settings')

    def submit(self, id, file, lang='c++'):
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
                'sourceCode': file.read(),
                'csrf_token': c,
            },
        )
        s = BeautifulSoup(r.content, 'html.parser')
        sid = s.select_one('.table-responsive td.submission-score').attrs.get(
            'data-id'
        )
        return '%s/%s' % (contest, sid)

    def _parse_stat(self, stat):
        if stat == 'CE':
            st = Submission.COMPILATION_ERROR
        elif stat in {'MLE', 'RE', 'OLE', 'IE'}:
            st = Submission.RUNTIME_ERROR
        elif stat == 'TLE':
            st = Submission.TIME_LIMIT_EXCEEDED
        elif stat == 'WA':
            st = Submission.WRONG_ANSWER
        elif stat == 'AC':
            st = Submission.ACCEPTED
        else:
            raise KeyError(stat)
        return st

    def wait_submission(self, id):
        contest, sid = id.split('/')
        while True:
            r = self.session.get(
                'https://atcoder.jp/contests/%s/submissions/%s'
                % (contest, sid)
            )
            s = BeautifulSoup(r.content, 'html.parser')
            sta = s.select_one('#judge-status span')
            stat = sta.text
            if stat == 'WJ' or '/' in stat:
                time.sleep(1)
                continue
            st = self._parse_stat(stat)
            msg = sta.attrs.get('title')
            dettab = sta.parent.parent.parent
            tds = dettab.select('td')
            sco = int(tds[4].text)
            tim = int(''.join(filter(lambda x: x.isdigit(), tds[7].text)))
            siz = int(''.join(filter(lambda x: x.isdigit(), tds[8].text)))
            v = dettab.parent.next_siblings
            dat = {}
            for t in v:
                if (
                    not isinstance(t, Tag)
                    or t.select_one('th') is None
                    or t.select_one('th').text.strip() != 'Case Name'
                ):
                    continue
                cases = t.select('tr')[1:]
                for c in cases:
                    name = c.select_one('td').text.strip()
                    dat[name] = self._parse_stat(
                        c.select_one('span').text.strip()
                    )
            return Submission(
                st,
                msg,
                sco,
                tim,
                siz,
                wrong=len(
                    list(filter(lambda x: dat[x] != Submission.ACCEPTED, dat))
                ),
                data=dat,
            )


class VJudgeSubmitter(Submitter):
    NAME = 'vjudge'

    PROBLEM_RE = re.compile('https?://vjudge.net/problem/(?P<p>.+)')

    def __init__(self):
        super().__init__()
        if not self.logged_in:
            self.logout()
            _load_or_get(self)

    @classmethod
    def _parse(cls, url):
        match = cls.PROBLEM_RE.match(url)
        if match:
            return 'VJ_%s' % match.group('p')

    @classmethod
    def _unparse(cls, id):
        try:
            VJ, prob = id.split('_')
            assert VJ == 'VJ'
        except:
            return
        return 'https://vjudge.net/problem/%s' % prob

    def login(self):
        self.session.post(
            'https://vjudge.net/user/login',
            data={'username': self.username, 'password': self.password},
        )

    @property
    def logged_in(self):
        return 'update-profile' in self.session.get('https://vjudge.net').text

    def submit(self, id, file, lang='c++'):
        d, n = tempfile.mkstemp()
        try:
            with open(d, 'w') as f:
                f.write(file.read())
            url = 'https://vjudge.net/problem/%s/origin' % id.partition('_')[2]
            r = self.session.get(url, stream=True)
            url = r.url
            return pickle.dumps(do_submit(n, url, lang))
        finally:
            os.remove(n)

    def wait_submission(self, id):
        return pickle.loads(id)


class USACOTrainingSubmitter(Submitter):
    NAME = 'usaco'

    def __init__(self):
        super().__init__()
        if not self.logged_in:
            self.logout()
            _load_or_get(self)

    @classmethod
    def _parse(cls, url):
        p = urllib.parse.urlparse(url)
        if p.netloc != 'train.usaco.org' or p.path != '/usacoprob2':
            return
        q = urllib.parse.parse_qs(p.query)
        if 'S' not in q:
            return
        return 'USACO_%s' % q['S'][0]

    @classmethod
    def _unparse(cls, id):
        try:
            USACO, pid = id.split('_')
            assert USACO == 'USACO'
        except:
            return
        return 'https://train.usaco.org/usacoprob2?S=%s' % pid

    def login(self):
        r = self.session.post(
            'https://train.usaco.org',
            data={
                'NAME': self.username,
                'PASSWORD': self.password,
                'SUBMIT': 'ENTER',
            },
        )
        a = r.text.index('?a=') + 3
        self._a = r.text[a : r.text.index('"', a)]

    @property
    def logged_in(self):
        if not hasattr(self, '_a'):
            return False
        r = self.session.get('https://train.usaco.org/?a=%s' % self._a)
        return 'Refresh this page' in r.text

    def submit(self, id, file, lang='c++'):
        r = self.session.post(
            'https://train.usaco.org/upload3',
            files={'filename': ('file', file), 'a': (None, self._a)},
        )
        s = (
            BeautifulSoup(r.content, 'html.parser')
            .select_one('div>font>div')
            .text
        )
        return s

    def wait_submission(self, id: str):
        if 'Compile: OK' not in id:
            return Submission(
                Submission.COMPILATION_ERROR,
                id[
                    id.index('did not compile correctly:')
                    + 26 : id.index('Compile errors;')
                ].strip(),
                0,
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
                time = id[
                    timei + len('%d: RUNTIME' % i) : id.index('>', timei)
                ]
                # memory=max(memory,float(id[p+1:id.index(' KB',p)]))
                return Submission(
                    Submission.TIME_LIMIT_EXCEEDED,
                    id[id.index('> Run %d' % i) : id.index('Full Test Data')]
                    .strip()
                    .replace('-' * 19 + '    ', '-' * 19 + '\n        '),
                    0,
                    time,
                    memory,
                    i,
                    {
                        'inurl': 'https://train.usaco.org/usacodatashow?a=%s'
                        % self._a,
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
            return Submission(
                Submission.ACCEPTED,
                id[i : id.index('\n\n', i)],
                100,
                time,
                memory,
            )
        if 'Test %d: BADCHECK' % i in id or 'Test %d: NOOUTPUT' % i in id:
            return Submission(
                Submission.WRONG_ANSWER,
                id[id.index('> Run %d' % i) : id.index('Full Test Data')]
                .strip()
                .replace('-' * 19 + '    ', '-' * 19 + '\n        '),
                0,
                time,
                memory,
                i,
                {
                    'inurl': 'https://train.usaco.org/usacodatashow?a=%s'
                    % self._a,
                    'outurl': 'https://train.usaco.org/usacodatashow?a=%s&i=out'
                    % self._a,
                },
            )
        raise ValueError(id)


def do_submit(file, url, lang='c++', verbose=False):
    for oj in OJS:
        if verbose:
            print('Trying', oj.NAME)
        pid = oj._parse(url)
        if pid is None:
            continue
        if verbose:
            print('Logging in with', oj.NAME)
        o = oj()
        if verbose:
            print('Submitting')
        sid = o.submit_file(pid, file, lang)
        sub = o.wait_submission(sid)
        _save_sess(o)
        return sub


OJS = {
    CodeforcesSubmitter,
    AtCoderSubmitter,
    VJudgeSubmitter,
    USACOTrainingSubmitter,
}
LANGUAGES = {'c++'}

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='submit to an OJ')
    ap.add_argument(
        'file',
        help='code file to read from',
    )
    ap.add_argument('url', help='problem source URL')
    ap.add_argument(
        '-l',
        '--lang',
        help='code language, default "c++"',
        choices=LANGUAGES,
        dest='lang',
        default='c++',
    )
    args = ap.parse_args()
    file = args.file
    url = args.url
    lang = args.lang

    sub = do_submit(file, url, lang, True)
    if sub is None:
        exit('Submission failed!')
    print('Status:               ', sub.status)
    if sub.score is not None:
        print('Score:                ', sub.score, '/ 100')
    if sub.time is not None:
        print('Time used:            ', sub.time, 'ms')
    if sub.memory is not None:
        print('Memory used:          ', sub.memory, 'KB')
    if sub.wrong is not None:
        print('Incorrect question(s):', sub.wrong)
    if sub.data is not None:
        print('Additional data:      ', sub.data)
    if sub.message is not None:
        if '\n' in sub.message:
            print('Message:\n')
            print(sub.message)
            print()
        else:
            print('Message:              ', sub.message)
