# -*- coding: utf-8 -*-
import os
import sys
#import logging
import logging.handlers
from logging import Formatter, StreamHandler, FileHandler, getLogger, DEBUG,INFO,WARN,CRITICAL,ERROR

import inspect
import configparser

CONFIG_FILE = '../config/zaif_coincheck_config.ini'
inifile = configparser.ConfigParser()
inifile.read(CONFIG_FILE, 'UTF-8')

class Logger:
	def __init__(self, name=__name__):

		self.system_log_level = inifile.get('system','loglevel')
		self.system_log_path = inifile.get('system','system_log_path')

		self.logger = getLogger(name)
		self.logger.setLevel(self.system_log_level)
		#self.logger.findCaller(True)


		# file
		if inifile.getboolean('system','logging') == True:
			self.file_logger = getLogger(name)
			self.file_logger.setLevel(self.system_log_level)
			self.file_logger.findCaller(True)

			handler = logging.handlers.TimedRotatingFileHandler(filename=self.system_log_path,when='D',backupCount=10)
			handler.setLevel(self.system_log_level)
			#file_formatter = Formatter("[%(asctime)s] [%(process)d] [%(name)s] [%(levelname)s] %(message)s")
			file_formatter = Formatter("[%(asctime)s] %(message)s")
			handler.setFormatter(file_formatter)
			self.file_logger.addHandler(handler)

		# stdout
		if inifile.getboolean('system','stdout') == True:

			self.logger = getLogger(name)
			self.logger.setLevel(self.system_log_level)
			self.logger.findCaller(True)

			#console_handler = StreamHandler(sys.stderr)
			console_handler = StreamHandler(sys.stdout)
			console_handler.setLevel(self.system_log_level)
			formatter = Formatter("[%(asctime)s] %(message)s")
			console_handler.setFormatter(formatter)
			self.logger.addHandler(console_handler)

		#　report log
		if inifile.getboolean('system','trade_log') == True:
			#レポートログ用ハンドラ設定
			self.trade_log_path = inifile.get('system','trade_log_path')
			self.trade_logger = getLogger(name)
			self.trade_logger.setLevel(self.system_log_level)

			#trade_handler = logging.handlers.FileHandler(filename=self.trade_log_path)
			trade_handler = logging.FileHandler(filename=self.trade_log_path)
			trade_handler.setLevel(self.system_log_level)
			trade_file_formatter = Formatter("%(asctime)s %(message)s")
			trade_handler.setFormatter(trade_file_formatter)
			self.trade_logger.addHandler(trade_handler)

	def debug(self, msg):
		self.logger.debug(self.getCallerInfo() + str(msg))
		#print(msg)

	def info(self, msg):
		if self.logger.level == DEBUG:
			debug_info = self.getCallerInfo() + msg
		else:
			debug_info = msg

		self.logger.info(debug_info)
		#print(msg)

	def warn(self, msg):
		if self.logger.level == DEBUG:
			debug_info = self.getCallerInfo() + msg
		else:
			debug_info = msg

		self.logger.warning(debug_info)
		#print(msg)

	def error(self, msg):
		if self.logger.level == DEBUG:
			debug_info = self.getCallerInfo() + msg
		else:
			debug_info = msg

		self.logger.error(debug_info)
		#print(msg)

	def critical(self, msg):
		if self.logger.level == DEBUG:
			debug_info = self.getCallerInfo() + msg
		else:
			debug_info = msg

		self.logger.critical(debug_info)
		#print(msg)

	def getCallerInfo(self):
		func = inspect.stack()[2].function
		fn = inspect.stack()[2].filename.split(os.sep)[-1]
		lineo = inspect.stack()[2].lineno
		return str(fn) + ":" + str(func) + ":" + str(lineo) + "\t"

	def tradelog(self,msg1):
		self.trade_logger.critical(str(msg1))



