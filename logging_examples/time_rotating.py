import time
import os
import gzip
import logging
from logging.handlers import TimedRotatingFileHandler
LOGGING_MSG_FORMAT = '%(name)-14s > [%(levelname)s] [%(asctime)s] : %(message)s'
LOGGING_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class GZipRotator:
    def __call__(self, source, dest):
        os.rename(source, dest)
        f_in = open(dest, 'rb')
        f_out = gzip.open("%s.gz" % dest, 'wb')
        f_out.writelines(f_in)
        f_out.close()
        f_in.close()
        os.remove(dest)

logging.basicConfig(level=logging.DEBUG, format=LOGGING_MSG_FORMAT, datefmt=LOGGING_DATE_FORMAT)
root_logger = logging.getLogger('')
logger = TimedRotatingFileHandler('time_rotating.log', when='m', interval=1, backupCount=3)
logger.suffix = '%d%m%Y_%H%M'
logger.namer = lambda name: name.replace(".log", "") + ".log"
logger.rotator = GZipRotator()
root_logger.addHandler(logger)

for i in range(6):
        logging.info("This is a test! %s", i)
        time.sleep(75)