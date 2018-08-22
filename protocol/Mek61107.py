#!/usr/bin/env python2
# coding: utf-8


class Mek61107:

	BAUDRATE_SYMBOLS = '012345' # Кодирование скорости передачи информации в режиме C
	BAUDRATES = (300,600,1200,2400,4800,9600)

	class Mek61107Exception(Exception):
		pass

	class SohOrStxExpected(Mek61107Exception):
		pass

	class WrongBcc(Mek61107Exception):
		pass

	class WrongIdMessage(Mek61107Exception):
		def __init__(self, buff):
			self.buff = buff
		def __str__(self):
			return 'Wrong id message: '+\
				(self.buff.decode('latin').encode('unicode_escape') if len(self.buff) > 0 else '<no data>')

	class WrongBaudrate(Mek61107Exception):
		def __init__(self, buff):
			self.buff = buff
		def __str__(self):
			return 'Wrong baudrate:'+self.buff.decode('latin').encode('unicode_escape')

	class WrongAckMessage(Mek61107Exception):
		def __init__(self, buff):
			self.buff = buff
		def __str__(self):
			return 'Wrong ack message: '+\
				(self.buff.decode('latin').encode('unicode_escape') if len(self.buff) > 0 else '<no data>')

	def __init__(self, initial_baudrate=300):
		self.initial_baudrate = initial_baudrate

	@staticmethod
	def calculate_bcc_iso1155(buff):
		ret = 0
		for b in buff:
			ret = (ret + ord(b)) & 0x7f
		ret ^= 0xFF
		return ret + 1

	@staticmethod
	def get_line(buff):
		"""Возвращает пустую строку или строку без разделителей строки"""
		endl_index = buff.find('\x0D\x0A')
		if endl_index >= 0:
			return buff[:endl_index]
		return ''

	@staticmethod
	def get_request(buff):
		"""Возвращает сообщение запроса; п.5.3
		для сообщения запроса buff.
		"""

		start_index = buff.find('/?')
		if not (start_index >= 0 and buff.endswith('!')):
			raise Mek61107.Mek61107Exception('Wrong request: '+buff.decode('latin').encode('unicode_escape'))
		return buff[start_index+2:-1]

	@staticmethod
	def make_request(device_number=''):
		"""Конструирует сообщение запроса; п.5.3
		device_number -- адрес устройства, до 32 символов: 0-9, A-Z, a-z, ' '
		"""
		return '/?'+str(device_number)+'!\x0D\x0A'

	@staticmethod
	def get_id_message(buff):
		"""Возвращает [company, baudrate, id] идентификационного сообщения п.5.3
		для идентификационного сообщения buff.
		Может вызвать исключения: WrongIdMessage, WrongBaudrate"""

		if len(buff) < 5 or not buff.startswith('/'):
			raise Mek61107.WrongIdMessage(buff)
		baudrate_index = Mek61107.BAUDRATE_SYMBOLS.find(buff[4])
		if not 0 <= baudrate_index < len(Mek61107.BAUDRATES):
			raise Mek61107.WrongBaudrate(buff)
		return buff[1:4], Mek61107.BAUDRATES[baudrate_index], buff[5:]

	@staticmethod
	def make_id_message(company, baudrate, id):
		"""Конструирует идентификационное сообщение п.5.3
		Может вызвать исключения: WrongIdMessage, WrongBaudrate"""

		company = str(company)
		if len(company) != 3:
			raise Mek61107.WrongIdMessage('len(company) != 3: "'+company+'"')
		id = str(id)
		if len(id) > 16:
			raise Mek61107.WrongIdMessage('len(id) > 16: "'+id+'"')
		try:
			baudrate_index = Mek61107.BAUDRATES.index(baudrate)
		except ValueError:
			raise Mek61107.WrongBaudrate(str(baudrate))
		if not 0 <= baudrate_index < len(Mek61107.BAUDRATE_SYMBOLS):
			raise Mek61107.WrongBaudrate(str(baudrate))
		return '/'+company+Mek61107.BAUDRATE_SYMBOLS[baudrate_index]+id+'\x0D\x0A'

	@staticmethod
	def get_ack_message(buff):
		"""Возвращает [baudrate, v, y] сообщения подтверждения/выбора опций; п.5.3
		для идентификационного сообщения buff.
		"""

		if len(buff) != 4 or not buff.startswith('\x06'):
			raise Mek61107.WrongIdMessage(buff)
		baudrate_index = Mek61107.BAUDRATE_SYMBOLS.index(buff[2]) # z
		if not 0 <= baudrate_index < len(Mek61107.BAUDRATES):
			raise Mek61107.WrongBaudrate(buff)
		return Mek61107.BAUDRATES[baudrate_index], buff[1], buff[3]

	@staticmethod
	def make_ack_message(baudrate, v='0', y='0'):
		"""Конструирует сообщение подтверждения/выбора опций; п.5.3
		baudrate -- 300,600,..
		v -- Управляющий символ: процедура протокола: '0' - нормальная; '1' - вторичная
		y -- Управляющий символ: '0' - считывание данных; '1' - режим программирования
		"""

		baudrate_index = Mek61107.BAUDRATES.index(baudrate)
		if baudrate_index < 0 or baudrate_index >= len(Mek61107.BAUDRATE_SYMBOLS):
			raise Mek61107.WrongBaudrate(str(baudrate))
		return '\x06'+v+Mek61107.BAUDRATE_SYMBOLS[baudrate_index]+y+'\x0D\x0A'

	class CommandBase:
		def __init__(self, is_block=False):
			self.is_block = is_block
			self.is_command = False
			self.is_message = False
			self.is_ack = False
			self.is_nak = False
		def serialize(self):
			return ''

	class Ack(CommandBase):
		def __init__(self):
			Mek61107.CommandBase.__init__(self)
			self.is_ack = True
		def __str__(self):
			return 'ACK'
		def serialize(self, calculate_bcc_func):
			return '\x06'

	class Nak(CommandBase):
		def __init__(self):
			Mek61107.CommandBase.__init__(self)
			self.is_nak = True
		def __str__(self):
			return 'NAK'
		def serialize(self, calculate_bcc_func):
			return '\x0F'

	class Message(CommandBase):
		def __init__(self, data, is_block=False):
			Mek61107.CommandBase.__init__(self, is_block=is_block)
			self.data = data
			self.is_message = True
		def __str__(self):
			return 'Message: '+self.data.decode('latin').encode('unicode_escape')
		def serialize(self, calculate_bcc_func):
			buff = '\x02'+self.data+('\x04' if self.is_block else '\x03')
			buff += chr(calculate_bcc_func(buff[1:]))
			return buff

	class Command(Message):
		def __init__(self, command, data, is_block=False):
			Mek61107.Message.__init__(self, data, is_block=is_block)
			self.command = command
			self.is_command = True
		def __str__(self):
			return 'Command: '+self.command+'; data: '+self.data.decode('latin').encode('unicode_escape')
		def serialize(self, calculate_bcc_func):
			buff = '\x01'+self.command+'\x02'+self.data+('\x04' if self.is_block else '\x03')
			buff += chr(calculate_bcc_func(buff[1:]))
			return buff

	def parse(self, buff):
		"""Processes buff and returns:
		- instance of classes: Ack, Nak, Message, Command;
		- None - buff not contain valid data
		- raise exceptions: WrongBcc, SohOrStxExpected"""

		is_command = False
		is_block = False
		if buff.startswith('\x01'):
			# SOH # Command
			is_command = True
		elif buff.startswith('\x02'):
			# STX # Message
			pass
		elif buff.startswith('\x06'):
			# ACK
			return self.Ack()
		elif buff.startswith('\x0F'):
			# NAK
			return self.Nak()
		else:
			raise Mek61107.SohOrStxExpected()
		# find ETX or EOT
		end_index = buff.find('\x03') # ETX
		if end_index < 0:
			end_index = buff.find('\x04') # EOT
			is_block = end_index >= 0
		if end_index >= 0 and len(buff) > end_index+1:
			# command or message recieved
			if not self.is_bcc_correct(buff, end_index):
				raise Mek61107.WrongBcc()
			if is_command:
				return self.Command(buff[1:3], buff[4:end_index])
			return self.Message(buff[1:end_index])
		return None

	def is_bcc_correct(self, buff, end_index, start_index=1):
		"""Successor can override this BCC calculation"""
		return calculate_bcc_iso1155(buff[start_index:end_index+1]) == ord(buff[end_index+1])
