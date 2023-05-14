import io
import os
from typing import Optional

from bs4 import Tag

__all__ = ['get_captcha', 'get_text']


def get_captcha(image: bytes) -> Optional[str]:
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(image))
    except:
        return
    # PyQt5
    try:
        raise NotImplementedError  # Skip PyQt5
        from PIL.ImageQt import toqpixmap
        from PyQt5.QtWidgets import (
            QApplication,
            QLabel,
            QLineEdit,
            QMainWindow,
            QPushButton,
        )

        app = QApplication([])
        win = QMainWindow()
        scale = ceil(100 / min(im.width, im.height))
        im = im.resize((im.width * scale, im.height * scale)).convert('RGBA')
        win.resize(im.width, im.height + 20)
        win.setWindowTitle('Enter captcha')
        lbl = QLabel(win)
        lbl.setGeometry(0, 0, im.width, im.height)
        lbl.setPixmap(toqpixmap(im))
        ed = QLineEdit(win)
        ed.setGeometry(0, im.height, im.width - 40, 20)
        btn = QPushButton('Enter', win)
        btn.setGeometry(im.width - 40, im.height, 40, 20)
        value = None

        def _qt_callback(_):
            nonlocal value
            value = ed.text()
            win.hide()
            win.destroy()
            app.quit()

        btn.clicked.connect(_qt_callback)
        win.show()
        app.exec_()
        return value or None
    except:
        pass
    # Fallback
    fn = None
    try:
        import tempfile

        d, fn = tempfile.mkstemp('.png')
        with open(d, 'wb') as f:
            im.save(f, 'PNG')
        print('Image file saved at:')
        print(fn)
        return (
            input('Please identify the captcha in the file and type it here: ').strip()
            or None
        )
    except:
        return
    finally:
        if fn is not None:
            os.remove(fn)


def get_text(tag, blocks=['p', 'div', 'table', 'h1', 'h2', 'h3', 'li', 'pre']):
    # https://stackoverflow.com/a/66835172
    def _gen(tag, ns=False):
        for c in tag.children:
            if isinstance(c, str):
                yield (str(c) if ns else str(c).strip('\r\n')).replace('\r\n', '\n')
            elif isinstance(c, Tag):
                yield from '\n' if c.name.lower() == 'br' else _gen(
                    c, ns or c.name == 'pre'
                )
                if c.name.lower() in blocks:
                    yield '\n'

    return ''.join(_gen(tag))
