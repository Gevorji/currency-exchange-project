import logging
import os

APP_LOGGER_NAME = 'currencyExchangeApp'

def make_filter(level):

    def log_filter(logrec: logging.LogRecord):
        return True if logrec.levelno <= getattr(logging, level) else False

    return log_filter

log_dir = os.path.join(os.path.split(os.path.dirname(__file__))[0], 'logs')

if not os.path.exists(log_dir):
    os.mkdir(log_dir)

logconfig = {
    'version': 1,
    'loggers': {
        APP_LOGGER_NAME: {
            'level': 'INFO',
            'handlers': ['to_file']
        }
    },
    'handlers': {
        'to_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'verbose_logs',
            'filename': os.path.join(log_dir, 'currexch.log'),
            'maxBytes': 2**20,
            'backupCount': 1
        }
    },
    'filters': {
        'info_and_below': {
            '()': f'{__name__}.make_filter',
            'level': 'INFO'
        },
    },
    'formatters': {
        'plain_logs': {
            'format': '<<<%(levelname)s>>> \n%(message)s\n'
        },
        'verbose_logs': {
            'format': '[%(asctime)s] <<<%(levelname)s>>> %(name)s:%(module)s line-%(lineno)s callable-%(funcName)s \n%(message)s\n',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    }
}
