import logging
import sys

def make_filter(level):

    def log_filter(logrec: logging.LogRecord):
        return True if logrec.levelno <= getattr(logging, level) else False

    return log_filter


logconfig = {
    'version': 1,
    'loggers': {
        'currencyExchangeApp': {
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
