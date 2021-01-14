# -*- coding: utf-8 -*-
import os
import sys
import logging
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
		self.logger.findCaller(True)

		self.file_logger = getLogger(name)
		self.file_logger.setLevel(self.system_log_level)
		self.file_logger.findCaller(True)


		#レポートログ用ハンドラ設定
		self.report_log_path = inifile.get('system','report_log_path')
		self.report_logger = getLogger('report')
		self.report_logger.setLevel(self.system_log_level)


		# file
		if inifile.getboolean('system','logging') == True:
			handler = logging.handlers.TimedRotatingFileHandler(filename=self.system_log_path,when='D',backupCount=10)
			handler.setLevel(self.system_log_level)
			file_formatter = Formatter("[%(asctime)s] [%(process)d] [%(name)s] [%(levelname)s] %(message)s")
			handler.setFormatter(file_formatter)
			self.file_logger.addHandler(handler)

		# stdout
		if inifile.getboolean('system','stdout') == True:
			#console_handler = StreamHandler(sys.stderr)
			console_handler = StreamHandler(sys.stdout)
			console_handler.setLevel(self.system_log_level)
			formatter = Formatter("[%(asctime)s] %(message)s")
			console_handler.setFormatter(formatter)
			self.logger.addHandler(console_handler)

		#　report log
		if inifile.getboolean('system','report_log') == True:
			report_handler = logging.handlers.TimedRotatingFileHandler(filename=self.report_log_path,when='W0',backupCount=10)
			report_handler.setLevel(self.system_log_level)
			report_file_formatter = Formatter("%(asctime)s %(message)s")
			report_handler.setFormatter(report_file_formatter)
			self.report_logger.addHandler(report_handler)



	def debug(self, msg):
		self.logger.debug(self.getCallerInfo() + msg)
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

	def report(self,msg1,msg2,msg3,msg4,msg5,msg6):
		self.report_logger.critical(str(msg1) + ',' + str(msg2) + ',' + str(msg3) + ',' + str(msg4) + ',' + str(msg5) + ',' + str(msg6))



