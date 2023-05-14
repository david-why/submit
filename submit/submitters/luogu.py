import re
import time

from ..base import Case, Language, Problem, Submission, SubmitterBase, TextType, Verdict
from ..util import get_captcha

__all__ = ['LuoguSubmitter']


class LuoguSubmitter(SubmitterBase):
    name = 'luogu'
    LANG = {Language.C__: 12, Language.PYTHON3: 25}
    VERDICTS = [
        None,  # Waiting
        None,  # Judging
        Verdict.COMPILATION_ERROR,
        Verdict.RUNTIME_ERROR,  # Output Limit Exceeded
        Verdict.MEMORY_LIMIT_EXCEEDED,
        Verdict.TIME_LIMIT_EXCEEDED,
        Verdict.WRONG_ANSWER,
        Verdict.RUNTIME_ERROR,
        None,
        None,
        None,
        Verdict.OTHER_FAIL,
        Verdict.ACCEPTED,
        None,
        Verdict.WRONG_ANSWER,  # Unaccepted
        Verdict.UNKNOWN,  # [-1], Unshown
    ]

    CRE = re.compile(
        r'https?://(?:www.)luogu.com.cn/problem/([A-Z0-9]+)\?contestId=([0-9]+)'
    )
    RE = re.compile('https?://(?:www.)luogu.com.cn/problem/([A-Z0-9]+)')

    @classmethod
    def parse_problem_url(cls, url):
        # https://www.luogu.com.cn/problem/P1234?contestId=56789
        match = cls.CRE.match(url)
        if match:
            return match.group(1) + ':' + match.group(2)
        match = cls.RE.match(url)
        print(match)
        if not match:
            return
        return match.group(1)

    @classmethod
    def get_problem_url(cls, id):
        if ':' in id:
            return 'https://www.luogu.com.cn/problem/%s?contestId=%s' % (
                id.partition(':')[0],
                id.partition(':')[2],
            )
        return 'https://www.luogu.com.cn/problem/' + id.upper()

    @classmethod
    def search_problem(cls, text):
        match = cls.RE.search(text)
        if not match:
            return
        return match.group(1)

    def _csrf(self, r):
        ci = r.text.index('csrf-token" content="') + 21
        return r.text[ci : r.text.index('"', ci)]

    def login(self, username, password):
        self.session.cookies.set(
            'login_referer', 'https://www.luogu.com.cn/', domain='www.luogu.com.cn'
        )
        c = self._csrf(
            self.session.get(
                'https://www.luogu.com.cn/auth/login',
                headers={'referer': 'https://www.luogu.com.cn/'},
            )
        )
        cap = self.session.get(
            'https://www.luogu.com.cn/api/verify/captcha?_t=%f' % time.time(),
            headers={'referer': 'https://www.luogu.com.cn/auth/login'},
        )
        captcha = get_captcha(cap.content)
        if not captcha:
            return False
        r = self.session.post(
            'https://www.luogu.com.cn/api/auth/userPassLogin',
            json={'captcha': captcha, 'password': password, 'username': username},
            headers={
                'x-csrf-token': c,
                'origin': 'https://www.luogu.com.cn',
                'referer': 'https://www.luogu.com.cn/auth/login',
            },
        )
        if r.status_code >= 400 or 'syncToken' not in r.json():
            return False
        r = self.session.post(
            'https://www.luogu.org/api/auth/syncLogin',
            json={'syncToken': r.json()['syncToken']},
            headers={
                'origin': 'https://www.luogu.com.cn',
                'referer': 'https://www.luogu.com.cn/',
            },
        )
        return r.status_code < 400  # and 'uid' in r.json()

    def logout(self):
        self.session.post(
            'https://www.luogu.com.cn/api/auth/logout',
            headers={
                'x-csrf-token': self._csrf(
                    self.session.get('https://www.luogu.com.cn/')
                ),
                'origin': 'https://www.luogu.com.cn',
                'referer': 'https://www.luogu.com.cn/',
            },
        )
        return not self.logged_in

    @property
    def logged_in(self):
        r = self.session.get('https://www.luogu.com.cn/user/setting?_contentOnly=1')
        return r.json().get('currentTemplate') == 'UserSetting'

    def get_problem(self, id):
        r = self.session.get(
            self.get_problem_url(id), params={'_contentOnly': 1}
        ).json()
        problem = r['currentData']['problem']
        text = ''
        if problem.get('background'):
            text += '# 题目背景\n' + problem['background'].strip() + '\n\n'
        if problem.get('description'):
            text += '# 题目描述\n' + problem['description'].strip() + '\n\n'
        if problem.get('inputFormat'):
            text += '# 输入格式\n' + problem['inputFormat'].strip() + '\n\n'
        if problem.get('outputFormat'):
            text += '# 输出格式\n' + problem['outputFormat'].strip() + '\n\n'
        if problem.get('samples'):
            text += '# 输入输出样例\n'
            for i, sample in enumerate(problem['samples']):
                text += (
                    '## 输入 \\#%d\n```\n' % (i + 1)
                    + sample[0].strip()
                    + '\n```\n\n## 输出 \\#%d\n```\n' % (i + 1)
                    + sample[1].strip()
                    + '\n```\n\n'
                )
        if problem.get('hint'):
            text += '# 说明/提示\n' + problem['hint'].strip() + '\n\n'
        return Problem(
            id, text, TextType.MARKDOWN, list(map(tuple, problem.get('samples', [])))
        )

    def submit(self, id, code, lang):
        c = self._csrf(self.session.get(self.get_problem_url(id)))
        r = self.session.post(
            'https://www.luogu.com.cn/fe/api/problem/submit/' + id,
            json={'code': code, 'enableO2': 0, 'lang': self.LANG[lang]},
            headers={
                'x-csrf-token': c,
                'origin': 'https://www.luogu.com.cn',
                'referer': self.get_problem_url(id),
            },
        )
        return str(r.json()['rid'])

    def get_submission(self, id):
        r = self.session.get(
            'https://www.luogu.com.cn/record/' + id, params={'_contentOnly': 1}
        )
        data = r.json()['currentData']['record']
        if self.VERDICTS[data['status'] or 0] is None:
            return
        return Submission(
            id,
            self.VERDICTS[data['status']],
            data['problem']['pid'],
            data['score'],
            data['sourceCode'],
            data['time'],
            data['memory'],
            [
                Case(
                    x['time'],
                    x['memory'],
                    verdict=self.VERDICTS[x['status']],
                    message=x.get('description') or None,
                )
                for y in data['detail']['judgeResult']['subtasks']
                for k in sorted(y['testCases'])
                for x in [y['testCases'][k]]
            ],
            data['detail']['compileResult']['message'],
        )
