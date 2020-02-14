# Python interface to Lutron RadioRA Classic RS232 bridge
#
# NOT SUPPORTED
# - non-polling updates
# - second Chronos bridge
# - phantom buttons
# - scenes

import logging

import serial
import asyncio

import re
import functools
from functools import wraps
from threading import RLock

LOG = logging.getLogger(__name__)

TIMEOUT = 2  # serial timeout (seconds)
BAUD_RATE = 9600

MAX_ZONES = 32
MAX_DIMMER_LEVEL = 100

RS232_COMMANDS = {
    'power_on':          'BP,16,ON',
    'power_off':         'BP,17,OFF',
    'flash_on':          'SFM,16,ON',
    'flass_off':         'SFM,17,OFF',
    'switch_on':         'SSL,{zone},ON',       # SSL,<Zone Number>,<State>(,<Delay Time>){(,<System>)}
    'switch_off':        'SSL,{zone},OFF',
    'set_dimmer':        'SDL,{zone},{level}',  # SDL,<Zone Number>,<Dimmer Level>(,<Fade Time>){(,<System)}
    'zone_map':          'ZMPI',
    'zone_status':       'ZSI',
    'version':           'VERI',
    'monitor_zones_on':  'LZCMON',
    'monitor_zones_off': 'LZCMOFF',
    'monitor_controls':  'MBPM{on_off}',
    'monitor_zone_maps': 'ZMPM{on_off}',
}

RS232_RESPONSES = {
    'REV': 'REV,{master_version},{slave_version}',
    'LZC': 'LZC,{zone},{state},{system}',
    'ZMP': 'ZMP,{states},{system}',                           # ZMP,11001011001011001011001011001000,S1
    'MBP': 'MBP,{master_control},{button},{state},{system}',
}

STATE_ON = 'ON'
STATE_OFF = 'OFF'
STATE_CHANGE = 'CHG'

SYSTEM1 = 1
SYSTEM2 = 2

SERIAL_INIT_ARGS = {
    'baudrate': BAUD_RATE,
    'stopbits': serial.STOPBITS_ONE,
    'bytesize': serial.EIGHTBITS,
    'parity': serial.PARITY_NONE,
    'timeout': TIMEOUT,
    'write_timeout': TIMEOUT
}

class RadioRAControllerBase(object):
    """Base class for interacting with a RadioRA Classic RS232 controller"""

    def __init__(self, tty: str):
        LOG.warn(f"Attemping to connect to RadioRA Classic RS232 bridge at {tty}")
        self._tty = tty
        self._zones = []

    def zones(self):
        return self._zones

    def switch_all_on(self):
        raise NotImplemented()

    def switch_all_off(self):
        raise NotImplemented()

    def flash_on(self):
        raise NotImplemented()

    def flash_off(self):
        raise NotImplemented()

    def switch_on(self, zone: int, system = SYSTEM1):
        raise NotImplemented()

    def switch_off(self, zone: int, system = SYSTEM1):
        raise NotImplemented()

    def is_zone_on(self, zone: int, system = SYSTEM1):
        raise NotImplemented()

    def set_dimmer_level(self, zone: int, system = SYSTEM1):
        raise NotImplemented()

    def update(self):
        """Update any cached state by querying the controller for its current status"""
        raise NotImplemented()

    def _apply_zone_config(self, json: str):
        # foreach zone, apply JSON config
        for zone in self.zones:
            print(zone)
        raise NotImplemented()

    @property
    def is_bridged(self):
        return False # this currently does not support RadioRA Classic/Chronos Bridged Systems

    def _parse_response(self, response: str):
        """Parse response from the RS232 bridge into a dictionary"""
        data = {}
        results = response.split(',')
        command = results[0]
        data['command'] = command

        fields = RS232_RESPONSES[command].split(',')
        for i in range(len(fields)):
            if i > 0:
                field = fields[i].lstrip('{').rstrip('}')
                data[field] = results[i]
        return data

def get_radiora_controller(tty: str):
    """Get synchronous RadioRA Classic controller"""

    lock = RLock()

    def synchronized(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                return func(*args, **kwargs)
        return wrapper

    class RadioRAControllerSync(RadioRAControllerBase):
        """
        Synchronous version of RadioRA Classic control interface
        :param tty: serial port, i.e. '/dev/ttyUSB0'
        :return: synchronous implementation of amplifier control interface
        """
        def __init__(self, tty: str):
            super.__init(tty)

            self._port = serial.serial_for_url(tty, do_not_open=True, **SERIAL_INIT_ARGS)
            self._port.timeout = TIMEOUT
            self._port.write_timeout = TIMEOUT
            self._port.open()

            LOG.debug("RadioRA RS232 controller version = {}", self.sendCommand('version'))

        def _write(self, request):
            # clear
            self._port.reset_output_buffer()
            self._port.reset_input_buffer()

            LOG.debug(f"Sending '{request}'")
            self._port.write(request)
            self._port.flush()
            return
    
        def _read(self):
            result = bytearray()
            while True:
                c = self._port.read(1)
                if not c:
                 raise serial.SerialTimeoutException(
                            'Connection timed out! Last received bytes {}'.format([hex(a) for a in result]))
                result += c
                if len(result) > skip and result[-LEN_EOL:] == EOL:
                     break

            ret = bytes(result)
            LOG.debug(f"Received {ret}")
            return ret.decode('ascii')

        def sendCommand(self, command: str, args = {}):
            request = RS232_COMMANDS[command].format(**args)
            self._write(request)
            response = self._read()
            return self._parse_response(response)

        def update(self):
            """Update any cached state by querying the controller for its current status"""
            # NOTE: ZMP always returns state for all 32 zones, PLUS if it is a bridged system
            # it will return two sets, with ",S1" and ",S2" at the end of the result
            # this does not support bridged systems currently
            result = self._serial.sendCommand('zone_status')

            zone_states = result.split(',')
            # FIXME: iterate zones

        @synchronized
        def switch_all_on(self):
            self.sendCommand('power_on')

        @synchronized
        def switch_all_off(self):
            self.sendCommand('power_off')

        @synchronized
        def flash_on(self):
            self.sendCommand('flash_on')

        @synchronized
        def flash_off(self):
            self.sendCommand('flash_off')

        @synchronized
        def set_dimmer_level(self, zone: int, level: int, system = SYSTEM1):
            level = int(max(0, min(level, MAX_DIMMER_LEVEL)))
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            self.sendCommand('set_dimmer_level', args = { 'zone': zone, 'level': level })

        @synchronized
        def switch_on(self, zone: int, system = SYSTEM1):
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            self.sendCommand('switch_on', args = { 'zone': zone })

        @synchronized
        def switch_off(self, zone: int, system = SYSTEM1):
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            self.sendCommand('switch_off', args = { 'zone': zone })

    return RadioRAControllerSync(tty)

@asyncio.coroutine
def get_async_radiora_controller(tty, loop):
    """Get asynchronous RadioRA Classic controller
    :param tty: serial port, i.e. '/dev/ttyUSB0'
    :param loop: event loop
    """
    from serial_asyncio import create_serial_connection

    lock = asyncio.Lock()

    def locked_coroutine(coro):
        @asyncio.coroutine
        @wraps(coro)
        def wrapper(*args, **kwargs):
            with (yield from lock):
                return (yield from coro(*args, **kwargs))
        return wrapper

    class RadioRAControllerAsync(RadioRAControllerBase):
        """
        Asynch version of RadioRA Classic control interface
        """
        def __init__(self, tty: str, protocol):
            super.__init__(tty)
            self._protocol = protocol

            LOG.debug("RadioRA RS232 controller version = {}", self.sendCommand('version'))
        
        @locked_coroutine
        @asyncio.coroutine
        def update(self):
            return # FIXME

        @locked_coroutine
        @asyncio.coroutine
        def switch_all_on(self):
            yield from self.sendCommand('power_on')

        @locked_coroutine
        @asyncio.coroutine
        def switch_all_off(self):
            yield from self.sendCommand('power_off')

        @locked_coroutine
        @asyncio.coroutine
        def flash_on(self):
            yield from self.sendCommand('flash_on')

        @locked_coroutine
        @asyncio.coroutine
        def flash_off(self):
            yield from self.sendCommand('flash_off')

        @locked_coroutine
        @asyncio.coroutine
        def set_dimmer_level(self, zone: int, level: int, system = SYSTEM1):
            level = int(max(0, min(level, MAX_DIMMER_LEVEL)))
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            yield from self.sendCommand('set_dimmer_level', args = { 'zone': zone, 'level': level })

        @locked_coroutine
        @asyncio.coroutine
        def switch_on(self, zone: int, system = SYSTEM1):
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            yield from self.sendCommand('switch_on', args = { 'zone': zone })

        @locked_coroutine
        @asyncio.coroutine
        def switch_off(self, zone: int, system = SYSTEM1):
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            yield from self.sendCommand('switch_off', args = { 'zone': zone })

        @locked_coroutine
        @asyncio.coroutine
        def apply_zone_config(self, json: str):
            # foreach zone, apply JSON config
            raise NotImplemented()

        @locked_coroutine
        @asyncio.coroutine
        def sendCommand(self, command, args = {}):
            request = RS232_COMMANDS[command].format(**args)
            yield from self._protocol.send(request)
            response = yield from self._protocol.read()
            return self._parse_response(response)

    class RadioRAProtocolAsync(asyncio.Protocol):
        def __init__(self, loop):
            super().__init__()
            self._loop = loop
            self._lock = asyncio.Lock()
            self._transport = None
            self._connected = asyncio.Event(loop=loop)
            self.q = asyncio.Queue(loop=loop)

        def connection_made(self, transport):
            self._transport = transport
            self._connected.set()
            LOG.debug('port opened %s', self._transport)

        def data_received(self, data):
            asyncio.ensure_future(self.q.put(data), loop=self._loop)

        @asyncio.coroutine
        def send(self, request: bytes, skip=0):
            yield from self._connected.wait()
            result = bytearray()
            # Only one transaction at a time
            with (yield from self._lock):
                self._transport.serial.reset_output_buffer()
                self._transport.serial.reset_input_buffer()
                while not self.q.empty():
                    self.q.get_nowait()
                self._transport.write(request)
                try:
                    while True:
                        result += yield from asyncio.wait_for(self.q.get(), TIMEOUT, loop=self._loop)
                        if len(result) > skip and result[-LEN_EOL:] == EOL:
                            ret = bytes(result)
                            LOG.debug('Received "%s"', ret)
                            return ret.decode('ascii')
                except asyncio.TimeoutError:
                    LOG.error("Timeout during receiving response for command '%s', received='%s'", request, result)
                    raise

    _, protocol = yield from create_serial_connection(loop,
                                                      functools.partial(RadioRAProtocolAsync, loop),
                                                      tty,
                                                      **SERIAL_INIT_ARGS)
    return RadioRAControllerAsync(tty, protocol)