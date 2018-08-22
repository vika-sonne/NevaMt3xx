#!/usr/bin/env python2
# -*- coding: UTF-8 -*-

# Имитатор работы счётчика согласно МЭК 61107 и OBIS кодам

import sys, traceback
from datetime import datetime, timedelta
import socket
import serial
import time
import argparse
from protocol import NevaMt3xx


VERBOSE_LEVEL = 0

def dump(message, level=0, datetime_stamp=False, ignore_verbose_level=False):
	if VERBOSE_LEVEL <= level and not ignore_verbose_level:
		return
	if datetime_stamp:
		print datetime.now().isoformat()+' '+'\t'*level+message
	else:
		print datetime.now().strftime('%H:%M:%S.%f ')+'\t'*level+message

def dump_rcv(buff, message='', level=0):
	if VERBOSE_LEVEL <= level:
		return
	if len(message) > 0:
		print datetime.now().strftime('%H:%M:%S.%f')+'\t'*level+' >> '+message+': '+buff.decode('latin').encode('unicode_escape')
	else:
		print datetime.now().strftime('%H:%M:%S.%f')+'\t'*level+' >> '+buff.decode('latin').encode('unicode_escape')

def dump_snd(buff, message='', level=0):
	if VERBOSE_LEVEL <= level:
		return
	if len(message) > 0:
		print datetime.now().strftime('%H:%M:%S.%f')+'\t'*level+' << '+message+': '+buff.decode('latin').encode('unicode_escape')
	else:
		print datetime.now().strftime('%H:%M:%S.%f')+'\t'*level+' << '+buff.decode('latin').encode('unicode_escape')

class log:
	def log_rcv(self, data):
		dump_rcv(data)
	def log_snd(self, data):
		dump_snd(data)

DEFAULT_COM_PORT = 'COM1' if sys.platform.startswith('win') else 'ttyUSB0'
MODEM_SERVER_DEFAULT_IP='localhost' # IP address to connect to
MODEM_SERVER_DEFAULT_PORT=25535 # TCP port to connect to
METER_DEFAULT_COMPANY = 'TPC'
METER_DEFAULT_DEVICE = 'NEVAMT324.2303'
METER_DEFAULT_ADDRESS = ''
METER_DEFAULT_PASSWORD = '00000000' # MEK 61107 password

def set_defaultencoding_globally(encoding='utf-8'):
	assert sys.getdefaultencoding() in ('ascii', 'mbcs', encoding)
	import imp
	_sys_org = imp.load_dynamic('_sys_org', 'sys')
	_sys_org.setdefaultencoding(encoding)

set_defaultencoding_globally()

def pase_args():
	parser = argparse.ArgumentParser(description=u'Имитатор счётчика электроэнергии типа НЕВА МТ 3xx.', formatter_class=argparse.RawTextHelpFormatter)
	parser.add_argument('-p','--port',metavar='COM_PORT',default=DEFAULT_COM_PORT,
		help=u'com порт для работы со счётчиком'+str(DEFAULT_COM_PORT))
	parser.add_argument('--server-ip',metavar='IP_ADDRESS',
		help=u'IP адрес сервера для работы с модемом')
	parser.add_argument('--server-port',metavar='TCP_PORT',default=MODEM_SERVER_DEFAULT_PORT,
		help=u'TCP пот сервера для работы с модемом; по умолчанию: '+str(MODEM_SERVER_DEFAULT_PORT))
	parser.add_argument('--company',metavar='3_CHARS',default=METER_DEFAULT_COMPANY,
		help=u'трёхбуквенный код производителя; по умолчанию: '+str(METER_DEFAULT_COMPANY))
	parser.add_argument('--device',metavar='UP_TO_16_CHARS',default=METER_DEFAULT_DEVICE,
		help=u'идентификатор счётчика (не более 16 символов); по умолчанию: '+str(METER_DEFAULT_DEVICE))
	parser.add_argument('--password',metavar='PASSWORD',default=METER_DEFAULT_PASSWORD,
		help=u'пароль для работы со счётчиком; по умолчанию: "'+str(METER_DEFAULT_PASSWORD)+'"')
	parser.add_argument('--address',metavar='PASSWORD',default=METER_DEFAULT_ADDRESS,
		help=u'адрес счётчика; по умолчанию: "'+str(METER_DEFAULT_ADDRESS)+'"')
	parser.add_argument('-o', '--obis',metavar='OBIS:VALUE',type=str,nargs='*',
		help=u'OBIS код и значение')
	# parser.add_argument('--obis',metavar='OBIS',nargs='*',
	# 	help=u'OBIS код для передачи счётчику; например, дата: ГГММДД: "00.09.02*FF"')
	parser.add_argument('--init-data',metavar='STRING',
		help=u'данные для передачи счётчиком сразу после подключения; например: "imei:080255635\\nversion:1.0\\nD<<10 0 0<<\\n"')
	parser.add_argument('-v',action='count',default=0,help='verbose level: -v, -vv or -vvv (bytes); по умолчанию: -v')
	args = parser.parse_args()
	if VERBOSE_LEVEL > 0:
		dump('arguments:')
	for attribute, value in sorted(args.__dict__.items()):
		def is_numeric(v):
			return type(v) in [int, float]
		dump(('--' if len(attribute)>1 else '-')+
			attribute.replace('_','-')+
			'='+('' if is_numeric(value) else '"')+
			str(value)+('' if is_numeric(value) else '"'), 1)
	return args

def connect(protocol, ignore_meter_address=True):
	global VERBOSE_LEVEL
	dump('Connect')
	VERBOSE_LEVEL += 1
	# recieve the request
	meter_address = protocol.get_request(protocol.receive_line())
	if not ignore_meter_address and meter_address != args.address:
		raise Exception('Another meter address requested: '+str(meter_address)+'; current address: '+str(args.address))
	buff = protocol.make_id_message(args.company, 9600, args.device)
	dump_snd(buff)
	if connection is not None:
		connection.sendall(buff)
	else:
		port.write(buff)
	baudrate, v, y = protocol.get_ack_message(protocol.receive_line())
	if baudrate != 9600:
		raise Exception('Baudrate 9600 not acknowledged: '+str(baudrate))
	VERBOSE_LEVEL -= 1
	dump('done')

def login(protocol, password):
	global VERBOSE_LEVEL
	dump('Login')
	VERBOSE_LEVEL += 1
	cmd = protocol.receive()
	if not cmd.is_command or cmd.command != 'P0':
		raise Exception('Command "P0" expected')
	protocol.send(NevaMt3xx.NevaMt3xx.Command('P1', '('+password+')'))
	cmd = protocol.receive()
	VERBOSE_LEVEL -= 1
	dump('done' if cmd.is_ack else 'FAIL')
	return cmd.is_ack

def logout(protocol):
	dump('Logout')
	global VERBOSE_LEVEL
	VERBOSE_LEVEL += 1
	protocol.send(NevaMt3xx.NevaMt3xx.Command('B0', ''))
	time.sleep(.5)
	protocol.send(NevaMt3xx.NevaMt3xx.Command('B0', ''))
	VERBOSE_LEVEL -= 1
	dump('done')

class Obis():
	def __init__(self, obis, data=None):
		self.begin_index = obis.find('[')
		if self.begin_index >= 0:
			obis2 = obis[:self.begin_index].replace('.', '').replace('*', '')
			buff = obis[self.begin_index+1:-1]
			obis = obis2
			self.begin_index = len(obis)
			buff = buff.partition('..')
			self.begin_value = int(buff[0], 16)
			self.end_value = int(buff[2], 16)
		else:
			obis = obis.replace('.', '').replace('*', '')
		self.obis = obis
		self.data = data
	def __str__(self):
		return self.obis+('' if self.begin_index < 0 else '[{:02X}..{:02X}]'.format(self.begin_value,self.end_value))+': '+str(self.data)
	def match(self, obis):
		if self.begin_index < 0:
			return self.obis == obis
		if self.obis[:self.begin_index] != obis[:self.begin_index]:
			return False
		return self.begin_value <= int(obis[self.begin_index:], 16) <= self.end_value

class ObisList(list):
	def __init__(self, *args):
		list.__init__(self, *args)
	def get_obis(self, obis):
		obis = obis.replace('.', '').replace('*', '')
		for i in self:
			if i.match(obis):
				if i.data is not None:
					return i.data
				if i.obis == '000902FF': # Дата: ГГММДД
					return datetime.now().strftime('%y%m%d')
				if i.obis == '000901FF': # Время: ЧЧММСС
					return datetime.now().strftime('%H%M%S')
				return ''
		raise Exception('OBIS not found: '+str(obis))


args = pase_args()
VERBOSE_LEVEL = args.v

obis_list = ObisList()
for obis_value in args.obis:
	buff = obis_value.partition(':')
	obis_list.append(Obis(buff[0], buff[2] if buff[1] == ':' else None))

dump('START', datetime_stamp=True)
dump('OBIS list:')
for o in obis_list:
	dump(str(o), 1,ignore_verbose_level=True)
# sys.exit(-1)
connection = None
if args.server_ip is not None:
	connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server_address = (args.server_ip, args.server_port)
	dump('Connection to server: '+str(server_address))
	connection.connect(server_address)
else:
	if not sys.platform.startswith('win') and args.port.find('/') < 0:
		args.port = '/dev/'+args.port

	dump('Open serial port: '+str(args.port))
	port = serial.Serial(
		port=args.port,
		baudrate=9600,
		timeout=2,
		bytesize=serial.SEVENBITS,
		parity=serial.PARITY_EVEN,
		stopbits=serial.STOPBITS_ONE)

	if not port.is_open:
		port.open()

# obis.append(Obis('00.09.02*FF')) # Дата: ГГММДД
# obis.append(Obis('00.09.01*FF')) # Время: ЧЧММСС
# obis.append(Obis('60.01.01*FF', '9144')) # Адрес счетчика: XXXXXXXX
# obis.append(Obis('60.01.00*FF')) # Модель счетчика: XXXXXXXX
# obis.append(Obis('60.01.0A*FF')) # Место установки: XXXXXXXXXXXXXXXX
# obis.append(Obis('60.09.00*FF')) # Температура (НЕВА МТ323, НЕВА MT314 XXSR): XXX

try:
	l = log() if args.v > 1 else None
	if connection is not None:
		protocol = NevaMt3xx.NevaMt3xx_tcp(connection, l, args.v > 2)
		if args.init_data is not None:
			# connection.sendall(args.init_data)
			connection.sendall('imei:080255635\nversion:1.0\nD<<10 0 0<<\n')
	else:
		protocol = NevaMt3xx.NevaMt3xx_com(port, l, args.v > 2)
		if args.init_data is not None:
			# port.write(args.init_data)
			port.write('imei:080255635\nversion:1.0\nD<<10 0 0<<\n')
	while True:
		connect(protocol)
		protocol.send(NevaMt3xx.NevaMt3xx.Command('P0', '(00000000)'))
		cmd = protocol.receive()
		if not cmd.is_command or cmd.command != 'P1':
			raise Exception('Login fail: P1 command expected')
		if cmd.data != '('+args.password+')':
			raise Exception('Login rejected (wrong password): '+cmd.data[1:-1])
		protocol.send(NevaMt3xx.NevaMt3xx.Ack())

		while True:
			cmd = protocol.receive()
			if cmd.is_command:
				if cmd.command == 'R1':
					obis = cmd.data[:-2]
					obis_value = obis_list.get_obis(obis)
					print 'obis: ',str(obis)+': '+str(obis_value)
					protocol.send(NevaMt3xx.NevaMt3xx.Message(obis+'('+str(obis_value)+')'))
					# try:
					# 	obis = cmd.data[:-2]
					# 	obis_value = obis.get_obis(obis)
					# 	protocol.send(NevaMt3xx.NevaMt3xx.Message(obis+'('+str(obis_value)+')'))
					# except:
					# 	protocol.send(NevaMt3xx.NevaMt3xx.Message('(3)'))
				elif cmd.command == 'B0':
					break

	# logout(protocol)
except Exception as e:
	print u'ERROR: '+str(e)
	exc_type, exc_value, exc_traceback = sys.exc_info()
	traceback.print_tb(exc_traceback, file=sys.stderr)
	sys.exit(-1)
if port.isOpen():
	port .close()
