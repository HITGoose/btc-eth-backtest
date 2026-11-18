# BTC_BOUNDED_NETWORK_RETRY_V1
import urllib.request,urllib.error,http.client,socket,time
_base_urlopen=urllib.request.urlopen

def _transient_network_error(error):
 if isinstance(error,urllib.error.HTTPError):return error.code in (429,500,502,503,504)
 reason=error.reason if isinstance(error,urllib.error.URLError)else error
 return isinstance(reason,(ConnectionResetError,ConnectionAbortedError,TimeoutError,socket.timeout,http.client.RemoteDisconnected))

def _bounded_urlopen(*args,**kwargs):
 for attempt in range(4):
  try:return _base_urlopen(*args,**kwargs)
  except Exception as error:
   if attempt==3 or not _transient_network_error(error):raise
   delay=(2,4,8)[attempt]
   print('NETWORK_RETRY',attempt+1,'/ 3',type(error).__name__,'wait',delay,'seconds',flush=True)
   time.sleep(delay)

urllib.request.urlopen=_bounded_urlopen
