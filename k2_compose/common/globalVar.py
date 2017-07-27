class GlobalVar:
  debug = None


def set_debug():
  GlobalVar.debug = True

def get_debug():
  return GlobalVar.debug