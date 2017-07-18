import sys
import logging

def confirm_input(msg=''):
    print '%s' % (msg), 'Are you sure? [yN]',
    try:
        confirm = raw_input()
        if confirm.lower() not in ['y', 'yes']:
            logging.error("Aborted by user.")
            sys.exit(-1)
    except KeyboardInterrupt:
        logging.error("Aborted by user.")
        sys.exit(-1)
    else:
        return True
