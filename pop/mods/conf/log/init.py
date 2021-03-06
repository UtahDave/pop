'''
This sub is used to set up logging for pop projects and injects logging
options into conf making it easy to add robust logging
'''
# Import python libs
import logging


def __init__(hub):
    '''
    Set up variables used by the log subsystem
    '''
    hub.conf.log.LEVELS = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
        }


def conf(hub, name):
    '''
    Return the conf dict for logging, this should be merged OVER by the loaded
    config dict(s)
    '''
    #TODO: Make this more robust to handle more logging interfaces
    ldict = {
        'log_file':
            {
            'default': f'{name}.log',
            'help': 'The location of the log file',
            },
        'log_level':
            {
            'default': 'info',
            'help': 'Set the log level, either quiet, info, warning, or error',
            },
        'log_fmt_logfile':
            {
            'default': '%(asctime)s,%(msecs)03d [%(name)-17s][%(levelname)-8s] %(message)s',
            'help': 'The format to be given to log file messages',
            },
        'log_fmt_console':
            {
            'default': '[%(levelname)-8s] %(message)s',
            'help': 'The log formatting used in the console',
            },
        'log_datefmt':
            {
            'default': '%H:%M:%S',
            'help': 'The date format to display in the logs',
            },
        'log_plugin':
            {
            'default': 'basic',
            'help': 'The logging plugin to use',
            },
        }
    return ldict