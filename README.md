# submit
Submit your code to an online OJ with a simple command!

Read my blog article about this submitter [here](https://david.webook.club/2022/06/26/online-oj-submitter/)!

## Usage
```
usage: submit [-h] [-S SAVE_FILE] {login,get,submit} ...

submit code to online judges

positional arguments:
  {login,get,submit}

options:
  -h, --help            show this help message and exit
  -S SAVE_FILE, --save-file SAVE_FILE
                        session file, defaults to "~/.submitter.sess"
```

### `login`
```
usage: submit login [-h] [-S SAVE_FILE] [-u USERNAME] [-p PASSWORD] {atcoder,codeforces,cses,luogu,usaco_contest,usaco,vjudge}

login to an OJ

positional arguments:
  {atcoder,codeforces,cses,luogu,usaco_contest,usaco,vjudge}
                        OJ to login

options:
  -h, --help            show this help message and exit
  -S SAVE_FILE, --save-file SAVE_FILE
                        session file, defaults to "~/.submitter.sess"
  -u USERNAME, --username USERNAME
                        username on OJ
  -p PASSWORD, --password PASSWORD
                        password on OJ
```

### `get`
```
usage: submit get [-h] [-S SAVE_FILE] [-f {markdown,text,html}] problem

get problem details

positional arguments:
  problem               problem ID (oj:pid) or URL

options:
  -h, --help            show this help message and exit
  -S SAVE_FILE, --save-file SAVE_FILE
                        session file, defaults to "~/.submitter.sess"
  -f {markdown,text,html}, --format {markdown,text,html}
                        output format (markdown|text|html), default markdown
```

### `submit`
```
usage: submit submit [-h] [-S SAVE_FILE] [-l {c++,python3}] [-p PROBLEM] file

submit your code

positional arguments:
  file                  code file to read from

options:
  -h, --help            show this help message and exit
  -S SAVE_FILE, --save-file SAVE_FILE
                        session file, defaults to "~/.submitter.sess"
  -l {c++,python3}, --lang {c++,python3}
                        language of code (c++|python3), default c++
  -p PROBLEM, --problem PROBLEM
                        problem ID (oj:pid) or URL, default searches code for URL
```

## API Documentation
-- TODO --
