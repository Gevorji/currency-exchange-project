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
            'stream': 'sys.stderr'
        },
        'to_stdout': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'stream': 'sys.stdout'
        }
    }
    }
