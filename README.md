# NevaMt3xx
Serial interface access library of electric power consumption counter of "Neva MT 3xx" type by Taipit (Saint-Petersburg) manufacturing

# Нева МТ 3xx
Библиотека работы с последовательным портом счётчика потребления электроэнергии типа Нева МТ 3xx производства Тайпит (Санкт-Петербург). Работа с прибором учёта происходит согласно МЭК 61107 и [OBIS](http://www.dlms.com/documentation/listofstandardobiscodesandmaintenanceproces/index.html) кодам (кроме байта контрольной суммы пакета, он не соответствует МЭК 61107 (ISO 1155)). Использует [python 2](https://www.python.org/downloads/).

Требует установки пакетов:
1. [pySerial](https://pypi.org/project/pyserial/).
Установить можно используя [pip](https://pypi.org/project/pip/) в одну строку командного интерпритатора: `pip install pyserial`. При этом проконтролировать, что используется pip необходимой версии python (для Windows - запуск pip.exe из необходимой папки).

2. [argparse](https://pypi.org/project/argparse/).
Установка аналогично: `pip install argparse`.


А также имитатор работы счётчика электроэнергии для отладки и технологических прогонов сервисного п/о работы с этими счётчиками. Имитатор представляет сервер, ожидающий подключений по TCP порту. [Пример запуска имитатора](meter_imitator.sh) со списком значений для OBIS параметров.
