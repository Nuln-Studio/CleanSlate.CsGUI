_BACKEND_LOG_CB = None

def set_backend_log_callback(cb):
    global _BACKEND_LOG_CB
    _BACKEND_LOG_CB = cb

def backend_log(level: str, msg: str):
    log_item = {"level": level, "msg": msg}
    if _BACKEND_LOG_CB is not None:
        try:
            _BACKEND_LOG_CB(log_item)
        except Exception:
            print(log_item)
    else:
        print(log_item)
