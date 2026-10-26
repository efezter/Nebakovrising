"""Bounded snapshot transport and event journal; no append-only telemetry stream."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

from nebakov_voice_receiver import MARKER, decode_packet

MAX_PACKET_BYTES = 16384

def valid_path(path):
    if not isinstance(path,str) or len(path)>1024 or any(ord(c)<32 for c in path): return False
    return path.replace('\\','/').endswith('/nebakov_voice/telemetry.json')

def lua_path(path):
    if not valid_path(path): raise ValueError('Invalid private telemetry path')
    return '"'+path.replace('\\','/').replace('"','\\"')+'"'

class FileSnapshot:
    def __init__(self,path):
        self.path=Path(path);self.last_error=None
        self.fingerprint=self._fingerprint()  # Never replay a leftover snapshot on startup.

    def _fingerprint(self):
        try:
            s=self.path.stat();return s.st_mtime_ns,s.st_size
        except OSError:return None

    def poll(self):
        stamp=self._fingerprint()
        if stamp is None or stamp==self.fingerprint:return None
        try:
            with self.path.open('rb') as stream:
                before=os.fstat(stream.fileno())
                data=stream.read(MAX_PACKET_BYTES+1)
                after=os.fstat(stream.fileno())
            if len(data)>MAX_PACKET_BYTES:raise ValueError('Snapshot exceeds packet size limit')
            if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):return None
            packet=decode_packet(MARKER+data)
        except (OSError,ValueError,TypeError,KeyError,UnicodeError,IndexError) as error:
            # An overwrite may be observed between truncate/write/close. Retry
            # the same fingerprint; a partial packet never advances state.
            self.last_error=str(error)[:160];return None
        self.fingerprint=after.st_mtime_ns,after.st_size
        self.last_error=None
        return packet

class BoundedJournal:
    def __init__(self,path,max_bytes=2*1024*1024,backups=2):
        self.path=Path(path);self.max_bytes=max_bytes;self.backups=backups;self.handler=None

    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        # Normalize legacy oversized journals, retaining the newest records.
        for path in [self.path,*[Path(str(self.path)+f'.{i}') for i in range(1,self.backups+1)]]:
            if path.exists() and path.stat().st_size>self.max_bytes:
                with path.open('rb') as f:
                    f.seek(-self.max_bytes,2);data=f.read()
                data=data.partition(b'\n')[2]
                temp=path.with_name(path.name+'.trim.tmp');temp.write_bytes(data);temp.replace(path)
        self.handler=RotatingFileHandler(self.path,maxBytes=self.max_bytes,backupCount=self.backups,encoding='utf-8')
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        return self

    def write(self,text):
        self.handler.emit(logging.LogRecord('NebakovVoice',logging.INFO,'',0,text.rstrip('\n'),(),None))

    def __exit__(self,*args):
        self.handler.close()
