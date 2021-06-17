# Interactive Graphical System

UFSC [Computer Graphics (INE5420)](http://www.lapix.ufsc.br/ensino/computacao-grafica/) project using [Qt for Python](https://www.qt.io/qt-for-python).


## Installation

### User

1. Download the latest [release](https://github.com/RamAddict/INE5420-CG/releases) through [GitHub](https://github.com/RamAddict/INE5420-CG).
2. Install [Qt for Python](https://pypi.org/project/PySide2/): `pip install pyside2 --user`
3. Execute the main [app](pycg/app.py): `python3 pycg/app.py`

### Dev

Run these to setup and test a development environment:

```shell
$ # system-specific install of pyside2-uic
$ python -m venv venv
$ source venv/bin/activate
(venv) $ pip install pyside2 pytest
(venv) $ make clean test run
```
