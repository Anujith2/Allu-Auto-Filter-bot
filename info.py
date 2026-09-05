import re
from os import environ

id_pattern = re.compile(r'^.\d+$')

def is_enabled(value, default):
    if str(value).lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif str(value).lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# Bot Credentials
SESSION = environ.get('SESSION', 'Media_search')
API_ID = int(environ.get('API_ID', '1234567'))
API_HASH = environ.get('API_HASH', 'YOUR_API_HASH')
BOT_TOKEN = environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN')

# Stream / Download Server Base URL
URL = environ.get('URL', 'https://qualified-cherida-ideapad-12683dc3.koyeb.app')

# Admins & Provided Channel IDs
ADMINS = [int(admin) for admin in environ.get('ADMINS', '1727225499').split() if id_pattern.search(admin)]
LOG_CHANNEL = int(environ.get('LOG_CHANNEL', '-1002047197980'))
DATABASE_CHANNEL = int(environ.get('DATABASE_CHANNEL', '-1004389084027'))

# Verification Settings
IS_VERIFY = is_enabled(environ.get('IS_VERIFY', 'True'), True)
VERIFY_URL = environ.get('VERIFY_URL', 'linkshortify.com')
VERIFY_API = environ.get('VERIFY_API', '927f420bfcbeda36287288f7e98110467feedbef')
HOW_TO_VERIFY = environ.get('HOW_TO_VERIFY', 'https://t.me/How_or_Open_Link')

CHNL_LNK = environ.get('CHNL_LNK', 'https://t.me/Allutvserials')

