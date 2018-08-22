#!/usr/bin/env python2
# -*- coding: UTF-8 -*-

import sys, traceback
from datetime import datetime, timedelta
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
DEFAULT_PASSWORD = '00000000'

def set_defaultencoding_globally(encoding='utf-8'):
	assert sys.getdefaultencoding() in ('ascii', 'mbcs', encoding)
	import imp
	_sys_org = imp.load_dynamic('_sys_org', 'sys')
	_sys_org.setdefaultencoding(encoding)

set_defaultencoding_globally()

def pase_args():
	parser = argparse.ArgumentParser(description=u'Программирование счётчика электроэнергии типа НЕВА МТ 3xx.', formatter_class=argparse.RawTextHelpFormatter)
	parser.add_argument('-p','--port',metavar='COM_PORT',default=DEFAULT_COM_PORT,
		help=u'com порт для работы со счётчиком; по умолчанию: '+str(DEFAULT_COM_PORT))
	parser.add_argument('--password',metavar='PASSWORD',default=DEFAULT_PASSWORD,
		help=u'пароль для работы со счётчиком; по умолчанию: "'+str(DEFAULT_PASSWORD)+'"')
	parser.add_argument('--obis',metavar='OBIS',nargs='*',
		help=u'OBIS код для передачи счётчику; например, дата: ГГММДД: "00.09.02*FF"')
	parser.add_argument('-i','--id',action='store_true',help=u'показать идентификатор счётчика')
	parser.add_argument('--half-hours',metavar='DAYS_AGO',type=int,
		help=u'считать получасовой профайл глубиной дней: 0..127')
	parser.add_argument('--calc-half-hours',metavar='DAYS_AGO',type=int,
		help=u'считать получасовой профайл и рассчитать по тарифам глубиной дней: 0..127')
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

def connect(protocol):
	global VERBOSE_LEVEL
	dump('Connect')
	VERBOSE_LEVEL += 1
	company, device = protocol.connect()
	VERBOSE_LEVEL -= 1
	if args.id:
		print '{}\n{}'.format(company, device)
	dump('done')
	return company, device

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

def read_obis(protocol, obis):
	dump('OBIS '+obis)
	obis = obis.replace('.', '').replace('*', '')
	global VERBOSE_LEVEL
	VERBOSE_LEVEL += 1
	protocol.send(NevaMt3xx.NevaMt3xx.Command('R1', obis+'()'))
	cmd = protocol.receive()
	if not cmd.is_message:
		raise Exception('OBIS {} expected'.format(obis))
	if not cmd.data.startswith(obis+'('):
		raise Exception('Wrong OBIS, expected {}: {}'.format(obis, cmd.data))
	VERBOSE_LEVEL -= 1
	dump(cmd.data[len(obis):].strip('()'))
	return cmd.data[len(obis):].strip('()')

def write_obis(protocol, obis, data):
	dump('OBIS '+obis+': '+data)
	obis = obis.replace('.', '').replace('*', '')
	global VERBOSE_LEVEL
	VERBOSE_LEVEL += 1
	protocol.send(NevaMt3xx.NevaMt3xx.Command('W1', obis+'('+data+')'))
	cmd = protocol.receive()
	if cmd.is_message:
		raise Exception('Write OBIS {} error: {}'.format(obis, cmd.data))
	if cmd.is_nak or cmd.is_command:
		raise Exception('Write OBIS {} error'.format(obis))
	VERBOSE_LEVEL -= 1
	dump(str(cmd))

def read_half_hours(days_ago=0):
	'''
	days_ago -- 0..127
	returns list of day 48 half hour energies, W
	'''
	if 0 <= days_ago <= 127:
		buff = read_obis(protocol, '63.01.00*'+'{:02X}'.format(days_ago)) # Профиль нагрузки активной энергии получасовой: Х.Х.ХХ,...,Х.Х.ХХ (кВт, по 48 параметров: первые..последние 30 минут)
		half_hour_energies = buff.split(',')
		if len(half_hour_energies) != 48:
			raise Exception('Wrong 63.01.00 answer: '+str(buff))
		return half_hour_energies
	else:
		raise Exception('days_ago exceeded: '+str(days_ago))

def print_half_hours(half_hour_energies, date_stamp=datetime.now(), rows_delimiter='   '):

	def get_day_print(half_hour_energies, date_stamp):
		ret = [date_stamp.strftime('%Y.%m.%d')]
		for half_hour_energy, half_hour_index in zip(half_hour_energies, xrange(len(half_hour_energies))):
			t = timedelta(minutes=half_hour_index*30)
			if type(half_hour_energy) is list:
				ret.append(', '.join(['{:02.2f}'.format(float(e)/1000) if type(e) is not datetime else e.strftime('%H:%M') for e in half_hour_energy]))
			else:
				ret.append('{:02}:{:02} {}'.format(t.seconds/3600, t.seconds%3600/60, half_hour_energy))
		return ret

	date_stamp.replace(date_stamp.year, date_stamp.month, date_stamp.day, 0, 0, 0, 0)
	half_hour_index = 0
	if type(half_hour_energies) is list and type(half_hour_energies[0]) is list:
		print_lines = ['']*49 # date & 48 half hours
		for half_hour_energies2, days_ago in zip(half_hour_energies, xrange(len(half_hour_energies))):
			lines = get_day_print(half_hour_energies2, date_stamp-timedelta(days=days_ago))
			# print 'len(print_lines)=', len(print_lines)
			# print 'len(lines)=', len(lines)
			# print zip(lines, xrange(0, len(lines)))
			line_max_width = max([len(x) for x in lines])
			for line, i in zip(lines, xrange(len(lines))):
				if i == 0:
					# date
					print_lines[i] += line.ljust(line_max_width)
				else:
					# 48 half hours
					print_lines[i] += line.rjust(line_max_width)
				print_lines[i] += rows_delimiter if days_ago<len(half_hour_energies)-1 else ''
				# print '"'+line.ljust(15)+'"'
		for line in print_lines:
			print line
	else:
		for line in get_day_print(half_hour_energies, date_stamp):
			print line

def read_day_tariffs_energies(days_ago=0):
	'''
	days_ago -- 0..127
	returns list of day tariffs enirgies, kWh: [sum, T1, T2, T3, T4]
	'''
	if 0 <= days_ago <= 127:
		buff = read_obis(protocol, '0F.80.80*'+'{:02X}'.format(days_ago))
		day_energies = buff.split(',')
		if len(day_energies) != 5:
			raise Exception('Wrong 0F.80.80 answer: '+str(buff))
		return day_energies
	else:
		raise Exception('days_ago exceeded: '+str(days_ago))

def read_monts(monts_ago=0):
	'''monts_ago -- 0..12'''
	if 0 <= monts_ago <= 12:
		buff = read_obis(protocol, '0F.08.80*'+'{:02X}'.format(monts_ago)) # Активная энергия нарастающим итогом: XXXXX.X.XX,...,ХХХХХ.Х.ХХ (кВт/ч, по 5 параметров: параметров энергия Т0-суммарный тариф,Т1,Т2,Т3,Т4)
		mounts_energies = buff.split(',')
		if len(mounts_energies) != 5:
			raise Exception('Wrong 0F.08.80 answer: '+str(buff))
		return mounts_energies
	else:
		raise Exception('monts_ago exceeded: '+str(days_ago))

def calculate_half_hours(start=datetime.now(), stop=None, days_ago=0):
	'''returns list of list of 48 day's energies: [ [[sum, T1, T2, T3, T4]*48]*days ]'''
	def get_shedule_tariffs(obis, table_count):
		'''returns list of date sorted year tariff shedule: ['MMDDTT' (TT - tariff number 1..; 7F - ordinary day)]'''
		buff = read_obis(protocol, obis)
		ret = buff.split(',')
		if len(ret) != table_count:
			Exception('Incorrect OBIS {}: {}'.format(obis, buff))
		ret = [tariff for tariff in ret if int(tariff) != 0] # remove empty (not used)
		ret = sorted(ret) # sort by date
		return ret
	def get_year_shedule_tariff(year_tariffs_shedule, day):
		for year_day in year_tariffs_shedule:
			if year_day.startswith(day):
				return year_day[-2:] if int(year_day[-2:], 16) != 0x7F else None
		return None
	def get_day_shedule_tariffs(day_tariffs_shedule):
		'''returns list of 48 (one per half hour) day tariff indexes'''
		if len(day_tariffs_shedule) == 0:
			return [1]*48
		if len(day_tariffs_shedule) == 1:
			return [int(day_tariffs_shedule[0][-2:])]*48
		ret = []
		tariffs_index, next_tariff_index = len(day_tariffs_shedule)-1, 0
		for half_hour_index in xrange(48):
			half_hour = 30*half_hour_index # day minutes: 0..1410 = 00:00..23:30
			half_hour = '{:02}{:02}'.format(half_hour/60, half_hour%60)
			if next_tariff_index < len(day_tariffs_shedule) and day_tariffs_shedule[next_tariff_index].startswith(half_hour):
				tariffs_index = next_tariff_index
				next_tariff_index += 1
			ret.append(int(day_tariffs_shedule[tariffs_index][-2:]))
		return ret
	def get_tariffs_half_hours(request_date):
		'''returns list of day 48 half hours of list datetime & energies: [ [sum, T1, T2, T3, T4]*48 ]'''
		half_hours = []
		meter_date = datetime.date(datetime.strptime(read_obis(protocol, '00.09.02*FF'), '%y%m%d')) # ГГММДД
		# print 'request_date: ', request_date, '; meter_date: ', meter_date
		for date_changed_tries_counter in xrange(3):
			i = (meter_date-request_date).days
			if i < 0:
				Exception('Can\'t work at future: request date {}; meter date {}'.format(request_date, meter_date))
			# print 'days_ago: '+str(i)
			# get list of day tariffs enirgies, kWh: [sum, T1, T2, T3, T4]
			day_tariffs_energies = read_day_tariffs_energies(i)
			day_tariffs_energies = [long(float(e)*1000) for e in day_tariffs_energies] # kWh -> Wh
			# print 'day_tariffs_energies = ', day_tariffs_energies
			# get list of day 48 half hour energies, W
			day_half_hours = read_half_hours(i)
			# print 'half_hours = ', day_half_hours
			day = datetime.now().strftime('%m%d')
			tariff_index = get_year_shedule_tariff(year_tariffs_shedule, day)
			if tariff_index is not None:
				# special day - tried all day half hours as one tariff
				for half_hour in day_half_hours:
					tariff_index = long(tariff_index)
					if not (0 < tariff_index <= 4):
						raise Exception('Tariff index out of range (1..4): '+str(tariff_index))
					half_hour = long(half_hour)/2
					day_tariffs_energies[0] += half_hour # sum
					day_tariffs_energies[tariff_index] += half_hour # Tx
					half_hours.append(day_tariffs_energies[:])
			else:
				if len(day_tariff_indexes) != len(day_half_hours):
					raise Exception('Can\'t build day tariff table')
				for tariff_index, half_hour in zip(day_tariff_indexes, day_half_hours):
					if not (0 < tariff_index <= 4):
						raise Exception('Tariff index out of range (1..4): '+str(tariff_index))
					half_hour = long(half_hour)/2
					day_tariffs_energies[0] += half_hour # sum
					day_tariffs_energies[tariff_index] += half_hour # Tx
					# print 'half_hour, tariff_index = ', half_hour, tariff_index
					half_hours.append(day_tariffs_energies[:])
			# Check whether the meter date changed
			meter_date2 = datetime.date(datetime.strptime(read_obis(protocol, '00.09.02*FF'), '%y%m%d')) # ГГММДД
			if meter_date == meter_date2:
				break
			half_hours = []
			if date_changed_tries_counter > 1:
				Exception('Can\'t read date')
			meter_date = meter_date2
		return half_hours

	# get half hours & using it according to the tariff table
	# get list of date sorted year tariff shedule: ['MMDDTT' (TT - tariff number 1..; 7F - ordinary day)]
	year_tariffs_shedule = get_shedule_tariffs('0B.00.00*FF', 32)
	# print 'year_tariffs_shedule = ', year_tariffs_shedule
	# get list of 48 (one per half hour) day tariff indexes
	day_tariff_indexes = get_day_shedule_tariffs(get_shedule_tariffs('0A.01.64*FF', 8))
	# print 'day_tariff_indexes = ', day_tariff_indexes
	half_hours = []
	if stop is None:
		if days_ago == 0:
			stop = datetime(start.year, start.month, start.day, 23, 59, 59)
		else:
			stop = start-timedelta(days=days_ago)
	# print 'start:', start, '; stop:', stop
	start_date = datetime.date(start)
	stop_date = datetime.date(stop)
	date = start_date
	while date >= stop_date:
		# get list (48 half hour) of list (5: sum, T1, T2, T3, T4)
		start_half_hour_index, stop_half_hour_index = 0, 47 # indexes, inclusive
		half_hours2 = get_tariffs_half_hours(date) # [ [sum, T1, T2, T3, T4]*48 ]
		# add datetime: [ [sum, T1, T2, T3, T4]*48 ] -> [ [datetime, sum, T1, T2, T3, T4]*48 ]
		half_hours2 = [[datetime(date.year, date.month, date.day, hh_index/2, hh_index*30%60)]+hh for hh, hh_index in zip(half_hours2, xrange(len(half_hours2)))]
		# print 'len(half_hours2): ', len(half_hours2), '; half_hours2: ', half_hours2
		if date == start_date:
			t = start-datetime(date.year, date.month, date.day)
			start_half_hour_index = t.seconds/1800 + (1 if t.seconds%1800 > 0 else 0)
			# print 'start_half_hour_index:', start_half_hour_index, '; t.seconds: ', t.seconds
		if date == stop_date:
			t = stop-datetime(date.year, date.month, date.day)
			stop_half_hour_index = t.seconds/1800
			# print 'stop_half_hour_index:', stop_half_hour_index, '; t.seconds: ', t.seconds
		half_hours.append(half_hours2[start_half_hour_index:stop_half_hour_index+1])
		# print 'half_hours2: ', half_hours2[start_half_hour_index:stop_half_hour_index+1]
		date -= timedelta(days=1)
	return half_hours


args = pase_args()
VERBOSE_LEVEL = args.v

if not sys.platform.startswith('win') and args.port.find('/') < 0:
	args.port = '/dev/'+args.port

dump('START', datetime_stamp=True)
dump('Open '+str(args.port))

port = serial.Serial(
	port=args.port,
	baudrate=9600,
	timeout=2,
	bytesize=serial.SEVENBITS,
	parity=serial.PARITY_EVEN,
	stopbits=serial.STOPBITS_ONE)

if not port.is_open:
	port.open()

try:
	l = log() if args.v > 1 else None
	protocol = NevaMt3xx.NevaMt3xx_com(port, l, args.v > 2)
	connect(protocol)
	if not login(protocol, args.password):
		raise Exception('Access denied')

	if args.obis is not None:
		for obis in args.obis:
			print read_obis(protocol, obis)

	# buff = read_obis(protocol, '00.09.02*FF') # Дата: ГГММДД
	# buff = read_obis(protocol, '60.01.01*FF') # Адрес счетчика: XXXXXXXX
	# buff = read_obis(protocol, '60.01.00*FF') # ID счетчика: XXXXXXXXXXXX
	# buff = read_obis(protocol, '60.01.04*FF') # Модель счетчика: XXXXXXXX
	# buff = read_obis(protocol, '60.01.0A*FF') # Место установки: XXXXXXXXXXXXXXXX
	# buff = read_obis(protocol, '60.09.00*FF') # Температура (НЕВА МТ323, НЕВА MT314 XXSR): XXX

	if args.half_hours is not None:
		if 0 <= args.half_hours <= 127:
			half_hours = []
			for i in xrange(0, args.half_hours+1):
				half_hours.append(read_half_hours(i))
			print_half_hours(half_hours, datetime.now())
		else:
			raise Exception('half-hours not in range 0..127: '+str(args.half_hours))

	elif args.calc_half_hours is not None:
		if 0 <= args.calc_half_hours <= 127:
			start = datetime.now()
			start = datetime(start.year, start.month, start.day)
			if args.calc_half_hours == 0:
				stop = start
			else:
				stop = start-timedelta(days=args.calc_half_hours)
			stop = datetime(stop.year, stop.month, stop.day, 23, 59, 59)
			# print 'start: ', start, 'stop: ', stop
			half_hours = calculate_half_hours(start=start, stop=stop)
			# print 'half_hours: ', half_hours
			for half_hour, half_hour_index in zip(half_hours, xrange(len(half_hours))):
				hh = 30*(half_hour_index%48) # day minutes: 0..1410 = 00:00..23:30
				hh = '{:02}:{:02}'.format(hh/60, hh%60)
			# add missing half hours into the list for correct print
			half_hours[0] = ['']*(48-len(half_hours[0]))+half_hours[0]
			# print half_hours[0]
			print_half_hours(half_hours, rows_delimiter=' | ')
		else:
			raise Exception('calc-half-hours not in range 0..127: '+str(args.calc_half_hours))

	# write_obis(protocol, '60.01.01*FF', '00009144') # Адрес счетчика: XXXXXXXX
	logout(protocol)
except Exception as e:
	print u'ERROR: '+str(e)
	exc_type, exc_value, exc_traceback = sys.exc_info()
	traceback.print_tb(exc_traceback, file=sys.stderr)
	sys.exit(-1)
if port.isOpen():
	port .close()
