import argparse
import getpass
import json
import os
import sys
import time

from submit.base import Language, TextType
from submit.submitter import Submitter
from submit.submitters import NAMES


def _problem(submitter, problem):
    ret = submitter.parse_problem_url(problem)
    if ret is not None:
        return ret
    ojn, prob = problem.split(':', 1)
    if ojn in NAMES:
        return NAMES[ojn], prob
    return None, problem


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        '-S',
        '--save-file',
        help='session file, defaults to "~/.submitter.sess"',
        default=os.path.join(os.path.expanduser('~'), '.submitter.sess'),
    )
    ap = argparse.ArgumentParser(
        prog='submit', description='submit code to online judges', parents=[common]
    )
    sp = ap.add_subparsers(required=True)

    def add_parser(name, description, **kwargs):
        return sp.add_parser(name, description=description, **kwargs, parents=[common])

    login = add_parser('login', description='login to an OJ')
    login.add_argument('oj', help='OJ to login', choices=list(NAMES))
    login.add_argument('-u', '--username', help='username on OJ')
    login.add_argument('-p', '--password', help='password on OJ')
    login.set_defaults(cmd='login')

    get = add_parser('get', description='get problem details')
    get.add_argument('problem', help='problem ID (oj:pid) or URL')
    get.add_argument(
        '-f',
        '--format',
        help='output format (markdown|text|html), default markdown',
        choices=['markdown', 'text', 'html'],
        type={
            'markdown': TextType.MARKDOWN,
            'text': TextType.TEXT,
            'html': TextType.HTML,
        }.get,
        default='markdown',
    )
    get.set_defaults(cmd='get')

    submit = add_parser('submit', description='submit your code')
    submit.add_argument(
        'file', help='code file to read from', type=argparse.FileType('r')
    )
    submit.add_argument(
        '-l',
        '--lang',
        help='language of code (c++|python3), default c++',
        choices=['c++', 'python3'],
        type={'c++': Language.C__, 'python3': Language.PYTHON3}.get,
        default='c++',
    )
    submit.add_argument(
        '-p',
        '--problem',
        help='problem ID (oj:pid) or URL, default searches code for URL',
    )
    submit.set_defaults(cmd='submit')

    ns = ap.parse_args(args)
    save = ns.save_file
    submitter = Submitter()
    if os.path.exists(save):
        with open(save) as f:
            submitter.load(json.load(f))
    if ns.cmd == 'login':
        ojn = ns.oj
        username = ns.username
        password = ns.password
        if username is None:
            username = input('Username: ')
        if password is None:
            password = getpass.getpass('Password: ')
        success = submitter.login(ojn, username, password)
        if success:
            print('Login successful!')
        else:
            print('Login failed, somehow...')
    elif ns.cmd == 'get':
        problem = ns.problem
        format = ns.format
        ojn, prob = _problem(submitter, problem)
        if ojn is None:
            ap.error('problem not found: %r' % problem)
        text = submitter.get_problem(ojn, prob)
        if text is None:
            ap.error('problem not found: %r' % (ojn, prob))
        print(text.get_as_type(format))
    elif ns.cmd == 'submit':
        file = ns.file
        lang = ns.lang
        problem = ns.problem
        code = file.read()
        if problem is None:
            parsed = submitter.search_problem(code)
            if parsed is None:
                ap.error('problem not found in code')
            ojn, prob = parsed
        else:
            ojn, prob = _problem(submitter, problem)
            if ojn is None:
                ap.error('problem not found: %r' % problem)
        if not isinstance(ojn, str):
            ojn = ojn.name
        print(ojn, prob, NAMES[ojn].get_problem_url(prob))
        subid = submitter.submit(ojn, prob, code, lang)
        print('Submission ID: %s' % subid)
        cnt = 0
        while True:
            submission = submitter.get_submission(ojn, subid)
            if submission is not None:
                break
            cnt += 1
            print('Waiting...', cnt, 's')
            time.sleep(1)
        print('Verdict:', submission.verdict.name)
        print('Score:  ', submission.score)
        if submission.time is not None:
            print('Time:   ', submission.time, 'ms')
        if submission.memory is not None:
            print('Memory: ', submission.memory, 'KB')
        if submission.data is not None:
            print('Additional data:')
            print(submission.data)
    with open(save, 'w') as f:
        json.dump(submitter.dump(), f)


if __name__ == '__main__':
    sys.exit(main())
