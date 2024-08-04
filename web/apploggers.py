import logging
import os
import sys

APP_LOGGER_NAME = 'currencyExchangeApp'


def make_filter(level):

    def log_filter(logrec: logging.LogRecord):
        return True if logrec.levelno <= getattr(logging, level) else False

    return log_filter


root_app_dir = os.path.split(os.path.dirname(__file__))[0]
print(root_app_dir)

if not os.path.exists(os.path.join(root_app_dir, 'logs')):
    log_dir = os.path.split(os.path.dirname(__file__))[0]


logconfig = {
    'version': 1,
    'loggers': {
        APP_LOGGER_NAME: {
            'level': 'INFO',
            'handlers': ['to_stderr', 'to_stdout']
        }
    },
    'handlers': {
        'to_stderr': {
            'class': 'logging.StreamHandler',
            'level': 'WARNING',
            'formatter': 'plain_logs',
            'stream': 'ext://sys.stderr'
        },
        'to_stdout': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'verbose_debug_logs',
            'filters': ['info_and_below'],
            'stream': 'ext://sys.stdout'
        },
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
        'verbose_debug_logs': {
            'format': '<<<%(levelname)s>>> %(name)s:%(module)s line-%(lineno)s callable-%(funcName)s \n%(message)s\n'
        }
    }
}
