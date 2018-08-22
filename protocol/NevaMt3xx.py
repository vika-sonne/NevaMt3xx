#!/usr/bin/env python2
# coding: utf-8

import Mek61107


class NevaMt3xx(Mek61107.Mek61107):
	"""Протокол работы со счётчиками НЕВА МТ3XХ"""

	def __init__(self, initial_baudrate=9600):
		Mek61107.Mek61107.__init__(self, initial_baudrate=initial_baudrate)

	def is_bcc_correct(self, buff, end_index, start_index=1):
		return NevaMt3xx.calculate_bcc_xor(buff[1:end_index+1]) == ord(buff[end_index+1])

	@staticmethod
	def calculate_bcc_xor(buff):
		ret = 0
		for b in buff:
			ret ^= ord(b)
		return ret


class LogBase:
	"""Abstract (interface) class. Used by NevaMt3xx_com & NevaMt3xx_tcp

	Example:
	from datetime import datetime
	from protocol import NevaMt3xx
	class Logger(NevaMt3xx.LogBase):
		def log_rcv(self, data):
			print datetime.now().strftime('%H:%M:%S.%f <<')+data.decode('latin').encode('unicode_escape')
		def log_snd(self, data):
			print datetime.now().strftime('%H:%M:%S.%f >>')+data.decode('latin').encode('unicode_escape')
	logger = Logger()
	...
	protocol = NevaMt3xx.NevaMt3xx_tcp(connection, log=logger, log_bytes=True)
	"""

	def log_rcv(self, data):
		pass
	def log_snd(self, data):
		pass


class NevaMt3xx_com(NevaMt3xx):
	"""Протокол работы со счётчиками НЕВА МТ3XХ по COM порту

	Example:
	import serial
	from protocol import NevaMt3xx
	port = serial.Serial(port='/dev/ttyUSB0',
		baudrate=9600, timeout=2,
		bytesize=serial.SEVENBITS,
		parity=serial.PARITY_EVEN,
		stopbits=serial.STOPBITS_ONE)
	protocol = NevaMt3xx.NevaMt3xx_com(port)
	try:
		# connect & login
		company, device = protocol.connect()
		cmd = protocol.receive()
		if not cmd.is_command or cmd.command != 'P0':
			raise Exception('Command "P0" expected')
		password = '00000000'
		protocol.send(NevaMt3xx.NevaMt3xx.Command('P1', '('+password+')'))
		cmd = protocol.receive()
		if not cmd.is_ack:
			raise Exception('Access denied')
		# Дата: ГГММДД
		protocol.send(NevaMt3xx.NevaMt3xx.Command('R1', '000902FF()'))
		cmd = protocol.receive()
		if not cmd.is_message:
			raise Exception('OBIS 000902FF expected')
		print cmd.data[8:].strip('()')
		# logout
		protocol.send(NevaMt3xx.NevaMt3xx.Command('B0', ''))
	except Exception as e:
		print u'ERROR: '+str(e)
	"""

	def __init__(self, port, log=None, log_bytes=False):
		NevaMt3xx.__init__(self)
		self.port = port
		self.log = log
		self.log_bytes = log_bytes

	def receive_line(self):
		buff = ''
		while True:
			buff2 = self.port.read(1)
			if len(buff2) == 0:
				return ''
			if self.log is not None and self.log_bytes:
				self.log.log_rcv(buff2)
			buff += buff2
			buff2 = self.get_line(buff)
			if len(buff2) > 0:
				if self.log is not None:
					self.log.log_rcv(buff)
				return buff2

	def connect(self, y='1', v='0'):
		buff = ''
		# посылка запроса
		if self.port.baudrate != self.initial_baudrate:
			self.port.baudrate = self.initial_baudrate
		buff = NevaMt3xx.make_request()
		if self.log is not None:
			self.log.log_snd(buff)
		self.port.write(buff)
		# приём индификационного сообщения
		buff = self.receive_line()
		company, baudrate, device = self.get_id_message(buff)
		if self.log is not None:
			self.log.log_rcv('Code: {}; baudrate: {}; id: {}'.format(company, baudrate, device))
		# посылка сообщения подтверждения/выбора опций
		buff = NevaMt3xx.make_ack_message(baudrate, v=v, y=y)
		if self.log is not None:
			self.log.log_snd(buff)
		self.port.write(buff)
		# обмен сообщениями
		if self.port.baudrate != baudrate:
			self.port.baudrate = baudrate
		return company, device

	def receive(self):
		buff = ''
		while True:
			buff2 = self.port.read(1)
			if len(buff2) == 0:
				return Mek61107.Mek61107.CommandBase()
			if self.log is not None and self.log_bytes:
				self.log.log_rcv(buff2)
			buff += buff2
			cmd = self.parse(buff)
			if cmd is not None:
				if self.log is not None:
					self.log.log_rcv(str(cmd))
				return cmd

	def send(self, cmd):
		buff = cmd.serialize(calculate_bcc_func=NevaMt3xx.calculate_bcc_xor)
		if self.log is not None:
			self.log.log_snd(str(cmd))
		self.port.write(buff)


class NevaMt3xx_tcp(NevaMt3xx):
	"""Протокол работы со счётчиками НЕВА МТ3XХ по tcp соединению

	Example:
	import socket
	from protocol import NevaMt3xx
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.bind('0.0.0.0', 14595)
	sock.listen(1)
	connection, client_address = sock.accept()
	protocol = NevaMt3xx.NevaMt3xx_tcp(connection)
	try:
		# connect & login
		company, device = protocol.connect()
		cmd = protocol.receive()
		if not cmd.is_command or cmd.command != 'P0':
			raise Exception('Command "P0" expected')
		password = '00000000'
		protocol.send(NevaMt3xx.NevaMt3xx.Command('P1', '('+password+')'))
		cmd = protocol.receive()
		if not cmd.is_ack:
			raise Exception('Access denied')
		# Дата: ГГММДД
		protocol.send(NevaMt3xx.NevaMt3xx.Command('R1', '000902FF()'))
		cmd = protocol.receive()
		if not cmd.is_message:
			raise Exception('OBIS 000902FF expected')
		print cmd.data[8:].strip('()')
		# logout
		protocol.send(NevaMt3xx.NevaMt3xx.Command('B0', ''))
	except Exception as e:
		print u'ERROR: '+str(e)
	"""

	def __init__(self, connection, log=None, log_bytes=True):
		NevaMt3xx.__init__(self)
		self.connection = connection
		self.log = log
		self.log_bytes = log_bytes

	def receive_line(self):
		buff = ''
		while True:
			buff2 = self.connection.recv(128)
			if len(buff2) == 0:
				return ''
			if self.log is not None and self.log_bytes:
				self.log.log_rcv(buff2)
			buff += buff2
			buff2 = self.get_line(buff)
			if len(buff2) > 0:
				if self.log is not None:
					self.log.log_rcv(buff)
				return buff2

	def connect(self, y='1', v='0'):
		buff = ''
		# посылка запроса
		buff = NevaMt3xx.make_request()
		if self.log is not None:
			self.log.log_snd(buff)
		self.connection.sendall(buff)
		# приём индификационного сообщения
		buff = self.receive_line()
		company, baudrate, device = self.get_id_message(buff)
		if self.log is not None:
			self.log.log_rcv('Code: {}; baudrate: {}; id: {}'.format(company, baudrate, device))
		# посылка сообщения подтверждения/выбора опций
		buff = NevaMt3xx.make_ack_message(baudrate, v=v, y=y)
		if self.log is not None:
			self.log.log_snd(buff)
		self.connection.sendall(buff)
		# обмен сообщениями
		return company, device

	def receive(self):
		buff = ''
		while True:
			buff2 = self.connection.recv(512)
			if len(buff2) == 0:
				return Mek61107.Mek61107.CommandBase()
			if self.log is not None and self.log_bytes:
				self.log.log_rcv(buff2)
			buff += buff2
			cmd = self.parse(buff)
			if cmd is not None:
				if self.log is not None:
					self.log.log_rcv(str(cmd))
				return cmd

	def send(self, cmd):
		buff = cmd.serialize(calculate_bcc_func=NevaMt3xx.calculate_bcc_xor)
		if self.log is not None:
			if self.log_bytes:
				self.log.log_snd(buff)
			self.log.log_snd(str(cmd))
		self.connection.sendall(buff)
