#---------------------------------------------------
# Copyright (c) 2016 Stefan Wendler
# Modified for additional options 2020 by devBioS 
#
# Licensed under the MIT License
#---------------------------------------------------
from machine import Pin, SPI
from os import uname


class MFRC522:

	OK = 0
	NOTAGERR = 1
	ERR = 2

	REQIDL = 0x26
	REQALL = 0x52
	AUTHENT1A = 0x60
	AUTHENT1B = 0x61

	def __init__(self, sck, mosi, miso, rst, cs):

		self.sck = Pin(sck, Pin.OUT)
		self.mosi = Pin(mosi, Pin.OUT)
		self.miso = Pin(miso)
		self.rst = Pin(rst, Pin.OUT)
		self.cs = Pin(cs, Pin.OUT)

		self.rst.value(0)
		self.cs.value(1)
		
		board = uname()[0]

		if board == 'esp32' or board == 'LoPy' or board == 'FiPy':
			self.spi = SPI(1, 10000000, sck=self.sck, mosi=self.mosi, miso=self.miso)
			self.spi.init()
		elif board == 'esp8266':
			self.spi = SPI(baudrate=100000, polarity=0, phase=0, sck=self.sck, mosi=self.mosi, miso=self.miso)
			self.spi.init()
		else:
			raise RuntimeError("Unsupported platform")

		self.rst.value(1)
		self.init()

	def _wreg(self, reg, val):

		self.cs.value(0)
		self.spi.write(b'%c' % int(0xff & ((reg << 1) & 0x7e)))
		self.spi.write(b'%c' % int(0xff & val))
		self.cs.value(1)

	def _rreg(self, reg):

		self.cs.value(0)
		self.spi.write(b'%c' % int(0xff & (((reg << 1) & 0x7e) | 0x80)))
		val = self.spi.read(1)
		self.cs.value(1)

		return val[0]

	def _sflags(self, reg, mask):
		self._wreg(reg, self._rreg(reg) | mask)

	def _cflags(self, reg, mask):
		self._wreg(reg, self._rreg(reg) & (~mask))

	def _tocard(self, cmd, send):

		recv = []
		bits = irq_en = wait_irq = n = 0
		stat = self.ERR

		if cmd == 0x0E:
			irq_en = 0x12
			wait_irq = 0x10
		elif cmd == 0x0C:
			irq_en = 0x77
			wait_irq = 0x30

		self._wreg(0x02, irq_en | 0x80)
		self._cflags(0x04, 0x80)
		self._sflags(0x0A, 0x80)
		self._wreg(0x01, 0x00)
		#print("send:")
		#print([hex(x) for x in send])
		for c in send:
			self._wreg(0x09, c)
		self._wreg(0x01, cmd)

		if cmd == 0x0C:
			self._sflags(0x0D, 0x80)

		i = 500 #2000
		while True:
			n = self._rreg(0x04)
			i -= 1
			if ~((i != 0) and ~(n & 0x01) and ~(n & wait_irq)):
				break

		self._cflags(0x0D, 0x80)

		if i:
			if (self._rreg(0x06) & 0x1B) == 0x00:
				stat = self.OK

				if n & irq_en & 0x01:
					stat = self.NOTAGERR
				elif cmd == 0x0C:
					n = self._rreg(0x0A)
					lbits = self._rreg(0x0C) & 0x07
					if lbits != 0:
						bits = (n - 1) * 8 + lbits
					else:
						bits = n * 8

					if n == 0:
						n = 1
					elif n > 16:
						n = 16

					for _ in range(n):
						recv.append(self._rreg(0x09))
			else:
				stat = self.ERR
		#print("recv:")
		#print(stat,[hex(x) for x in recv],bits)
		return stat, recv, bits

	def _crc(self, data):

		self._cflags(0x05, 0x04)
		self._sflags(0x0A, 0x80)

		for c in data:
			self._wreg(0x09, c)

		self._wreg(0x01, 0x03)

		i = 0xFF
		while True:
			n = self._rreg(0x05)
			i -= 1
			if not ((i != 0) and not (n & 0x04)):
				break

		return [self._rreg(0x22), self._rreg(0x21)]

	def init(self):

		self.reset()
		self._wreg(0x2A, 0x8D)
		self._wreg(0x2B, 0x3E)
		self._wreg(0x2D, 30)
		self._wreg(0x2C, 0)
		self._wreg(0x15, 0x40)
		self._wreg(0x11, 0x3D)
		self.antenna_on()

	def reset(self):
		self._wreg(0x01, 0x0F)

	def antenna_on(self, on=True):

		if on and ~(self._rreg(0x14) & 0x03):
			self._sflags(0x14, 0x03)
		else:
			self._cflags(0x14, 0x03)

	def request(self, mode):

		self._wreg(0x0D, 0x07)
		(stat, recv, bits) = self._tocard(0x0C, [mode])

		if (stat != self.OK) | (bits != 0x10):
			stat = self.ERR

		return stat, bits

	def requestRawAnswer(self, mode):

		self._wreg(0x0D, 0x07)
		(stat, recv, bits) = self._tocard(0x0C, [mode])

		if (stat != self.OK):
			stat = self.ERR

		return stat, recv, bits

	def anticoll(self):

		ser_chk = 0
		ser = [0x93, 0x20]

		self._wreg(0x0D, 0x00)
		(stat, recv, bits) = self._tocard(0x0C, ser)

		if stat == self.OK:
			if len(recv) == 5:
				for i in range(4):
					ser_chk = ser_chk ^ recv[i]
				if ser_chk != recv[4]:
					stat = self.ERR
			else:
				stat = self.ERR

		return stat, recv
	#PICC_HALT https://www.rubydoc.info/gems/mfrc522/0.0.1/Mfrc522#picc_halt-instance_method:
	def halt(self):
		PICC_HALT = 0x50
		buf = [PICC_HALT, 0x00]
		buf += self._crc(buf)
		(stat, recv, bits) = self._tocard(0x0C, buf)
		return self.OK if (stat == self.OK) and (bits == 0x18) else self.ERR	

	#PICC_WUPA =0x52
	#REQuest command, Type A. Invites PICCs in state IDLE to go to READY and prepare for anticollision or selection. 7 bit frame.
	def wake(self):
		PICC_WUPA = 0x52
		(stat, recv, bits) = self._tocard(0x0C, [PICC_WUPA])
		return self.OK if (stat == self.OK) and (bits == 0x18) else self.ERR


	def select_tag(self, ser):

		buf = [0x93, 0x70] + ser[:5]
		buf += self._crc(buf)
		(stat, recv, bits) = self._tocard(0x0C, buf)
		return self.OK if (stat == self.OK) and (bits == 0x18) else self.ERR

	def auth(self, mode, addr, sect, ser):
		return self._tocard(0x0E, [mode, addr] + sect + ser[:4])[0]

	def stop_crypto1(self):
		self._cflags(0x08, 0x08)

	def read(self, addr):

		data = [0x30, addr]
		data += self._crc(data)
		(stat, recv, _) = self._tocard(0x0C, data)
		return recv if stat == self.OK else None

	def write(self, addr, data):

		buf = [0xA0, addr]
		buf += self._crc(buf)
		(stat, recv, bits) = self._tocard(0x0C, buf)

		if not (stat == self.OK) or not (bits == 4) or not ((recv[0] & 0x0F) == 0x0A):
			stat = self.ERR
		else:
			buf = []
			for i in range(16):
				buf.append(data[i])
			buf += self._crc(buf)
			(stat, recv, bits) = self._tocard(0x0C, buf)
			if not (stat == self.OK) or not (bits == 4) or not ((recv[0] & 0x0F) == 0x0A):
				stat = self.ERR

		return stat

	def checkChinaUID(self):
		answer = False
		#try to send magic command to the sector 0 
		self.halt()
		(stat, data, bits) = self.requestRawAnswer(0x40) # request is 7 bits
		#print(stat, data, bits)
		if stat == self.OK and data[0] == 0xA:
			#if answer is 0xA, we check further... maybe this is a china changeable UID card
			answer=True 
			#--------------
			#if the next command didn't work, we're pretty sure that is a china card
			#disabled this as the above is enough to detect a china card
			#--------------
			#self._wreg(0x0D, 0x08) #send 8 bytes
			#(stat, data, bytes) = self._tocard(0x0C,[0x43])
			#if stat == self.OK and data[0] == 0xA:
				#sector unlocked. this is a china card
				#from here we can write sector 0 without authentication
			#	answer=True
			#--------------
		self.wake()
		return answer
		
	#https://learn.adafruit.com/adafruit-pn532-rfid-nfc/ndef
	def setKey(self,sector,keya,keyb):
		#https://www.az-delivery.de/blogs/azdelivery-blog-fur-arduino-und-raspberry-pi/zugangsbeschrankung-zu-geraten-per-contactless-card-mit-der-nodemcu-und-dem-rc522-modul-vierter-teil-down-the-rabbit-hole?ls=de&cache=false
		sectorkeytable = [3,7,11,15,19,23,27,31,35,39,43,47,51,55,59,63]
		key = []
		key.extend(keya[:6])
		key.append(0x78) #Data Block 0-3 Access Conditions: Key B write / Key A Read
		key.append(0x77) #KEY A & KEY B & Acces Bits Write:Key B  / Key A Read Access Bits
		key.append(0x88) #Calculator: http://calc.gmss.ru/Mifare1k/
		key.append(0x69) #Fixer Wert - > default hex 69
		key.extend(keyb[:6])
		
		#print(key)
		self.write(sectorkeytable[sector], key)
	def reSetKeyOpen(self,sector,keya,keyb):
		#https://www.az-delivery.de/blogs/azdelivery-blog-fur-arduino-und-raspberry-pi/zugangsbeschrankung-zu-geraten-per-contactless-card-mit-der-nodemcu-und-dem-rc522-modul-vierter-teil-down-the-rabbit-hole?ls=de&cache=false
		sectorkeytable = [3,7,11,15,19,23,27,31,35,39,43,47,51,55,59,63]
		key = []
		key.extend(keya[:6])
		key.append(0xFF) #Data Block 0-3 Access Conditions: Key B write / Key A Read
		key.append(0x07) #KEY A & KEY B & Acces Bits Write:Key B  / Key A Read Access Bits
		key.append(0x80) #Calculator: http://calc.gmss.ru/Mifare1k/
		key.append(0x69) #Fixer Wert - > default hex 69
		key.extend(keyb[:6])
		
		#print(key)
		self.write(sectorkeytable[sector], key)		