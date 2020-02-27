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
MAX_COMMAND_LEN = 22

ENCODING = 'ascii'

ON_FLAG = '1'
OFF_FLAG = '0'
UNKNOWN_FLAG = 'X'

RS232_COMMANDS = {
    'power_on':          'BP,16,ON',
    'power_off':         'BP,17,OFF',
    'flash_on':          'SFM,16,ON',
    'flash_off':         'SFM,17,OFF',
    'phantom_status':    'LMP',
    'phantom_on':        'BP,{button},ON',      # button: 1-15
    'phantom_off':       'BP,{button},OFF',     # button: 1-15
    'phantom_raise':     'RAISE,{button},{system}', # button: 1-15
    'phantom_lower':     'LOWER,{button},{system}', # button: 1-15
    'stop_raise_lower':  'STOPRL',
    'switch_on':         'SSL,{zone},ON',       # SSL,<Zone Number>,<State>(,<Delay Time>){(,<System>)}
    'switch_off':        'SSL,{zone},OFF',
    'set_dimmer_level':  'SDL,{zone},{level}',  # SDL,<Zone Number>,<Dimmer Level>(,<Fade Time>){(,<System)}
    'zone_map':          'ZMP,{zone_states}',
    'zone_map_inquiry':  'ZMPI',
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
    '!':   '!'  # response to some commands
}

STATE_ON = 'ON'
STATE_OFF = 'OFF'
STATE_CHANGE = 'CHG'

SYSTEM1 = 'S1'
SYSTEM2 = 'S2'

SERIAL_INIT_ARGS = {
    'baudrate':      BAUD_RATE,
    'stopbits':      serial.STOPBITS_ONE,
    'bytesize':      serial.EIGHTBITS,
    'parity':        serial.PARITY_NONE,
    'timeout':       TIMEOUT,
    'write_timeout': TIMEOUT
}

EOL = b"\r"
LEN_EOL = 1

class RadioRAControllerBase(object):
    """Base class for interacting with a RadioRA Classic RS232 controller"""

    def __init__(self, tty: str):
        LOG.debug(f"Connecting to RadioRA Classic RS232 bridge at {tty}")
        self._tty = tty
        self._cached_zone_status = None

    def sendCommand(self, command: str, args = {}):
        """Send raw RS232 command to the RadioRA Classic device"""
        raise NotImplemented()

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

    def set_dimmer_level(self, zone: int, level: int, system = SYSTEM1):
        """
        FROM LUTRON RS232 DOC: To control more than one zone, Lutron recommends using a Phantom Button because using Direct Zone Control Commands will result in slower and staggered system responses.
        """
        raise NotImplemented()

    def update(self):
        """Update any cached state by querying the controller for its current status"""
        raise NotImplemented()

    def zone_status(self) -> dict:
        # NOTE: ZMP always returns state for all 32 zones, PLUS if it is a bridged system
        # it will return two sets, with ",S1" and ",S2" at the end of the result
        # this does not support bridged systems currently
        #self._zone_status = result # FIXME
        raise NotImplemented()

    def _handle_zone_status(self, data) -> dict:
        if 'system' in data:
            LOG.warning("The second system in bridged RadioRA Classic systems are not supported, ignoring!")

        self._cached_zone_status = data
        return self._cached_zone_status

    def restore_zone_status(self, status: dict):
        """Given the response from a zone_status call, this will restore the current
        switch settings to the provided values (not including dimmer levels since Classic
        does not support this)"""
        raise NotImplemented()

    def is_zone_on(self, zone: int, system = SYSTEM1):
        """
        returns 0 if OFF, 1 if ON, and None if Unknown
        (based on previously cached data; call update() first to get current values)
        """
        raise NotImplemented()

    def _handle_is_zone_on(self, zone: int, system = SYSTEM1):
        if system == SYSTEM2:
            LOG.warning("The second system in bridged RadioRA Classic systems are not supported, ignoring!")
            return None

        if self._cached_zone_status is None:
            LOG.warning(f"Have not loaded zone status yet, cannot determine if zone {zone} is on!")
            return None

        zone_data = self._cached_zone_status.get(system)
        current_state = zone_data.get('states')

        if current_state:
            status = current_state[zone]
            if status == UNKNOWN_FLAG:
                return None
            else:
                return int(status)

    @property
    def is_bridged(self):
        return False # this currently does not support RadioRA Classic/Chronos Bridged Systems

    def _parse_response(self, response: str):
        """Parse response from the RS232 bridge into a dictionary"""
        data = {}
        LOG.debug(f"Parsing: {response}")

        results = response.split(',')
        command = results[0]
        if not command:
           LOG.error("RadioRA Classic response was empty")
           return None

        data['command'] = command
        pattern = RS232_RESPONSES.get(command)
        if pattern is None:
            LOG.error("Could not find RS232 response pattern for command {command}, ignoring")
            return None

        # convert RS232 response into dictionary based on the protocol pattern
        fields = pattern.split(',')
        for i in range(len(fields)):
            if i > 0 and i < len(results):
                field = fields[i].lstrip('{').rstrip('}')
                data[field] = results[i].rstrip(' ')

        LOG.debug(f"Parsed response: {data}")
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
            super().__init__(tty)

            self._port = serial.serial_for_url(tty, do_not_open=True, **SERIAL_INIT_ARGS)
            self._port.timeout = TIMEOUT
            self._port.write_timeout = TIMEOUT
            self._port.open()

        def _write(self, request):
            # clear
            self._port.reset_output_buffer()
            self._port.reset_input_buffer()

            LOG.debug(f"Sending: {request}")
            self._port.write(request)
            self._port.flush()
            return
    
        def _read(self, skip=0):
            result = bytearray()
            while True:
                c = self._port.read(1)
                if not c:
                 raise serial.SerialTimeoutException(
                            'Connection timed out! Last received bytes {}'.format([hex(a) for a in result]))
                result += c
                if len(result) > skip and result[-LEN_EOL:] == EOL:
                    result = result[:-LEN_EOL] # strip off end of line
                    break

            ret = bytes(result).decode(ENCODING)
            LOG.debug(f"Received: {ret}")
            return ret

        @synchronized
        def sendCommand(self, command: str, args = {}):
            request = bytes(RS232_COMMANDS[command].format(**args), ENCODING) + EOL
            self._write(request)
            response = self._read()
            return self._parse_response(response)

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

        @synchronized
        def zone_status(self) -> dict:
            response = self.sendCommand('zone_map_inquiry')
            if not response:
                LOG.warning(f"Failed updating RadioRA Classic zone status from {self._tty}")
                return None

            data = {}
            data[SYSTEM1] = response

            # handle multiple bridged zones
            if 'system' in response:
                response = self._read() # read second bridged status line
                data_s2 = self._parse_response(response)
                data[SYSTEM2] = data_s2

            return self._handle_zone_status(data)

        @synchronized
        def update(self):
            self.zone_status() # force update of the zone status
            return

        @synchronized
        def is_zone_on(self, zone: int, system = SYSTEM1):
            if not self._cached_zone_status:
                self.update()
            return self._handle_is_zone_on(zone, system)

    return RadioRAControllerSync(tty)

async def get_async_radiora_controller(tty, loop):
    """Get asynchronous RadioRA Classic controller
    :param tty: serial port, i.e. '/dev/ttyUSB0'
    :param loop: event loop
    """
    from serial_asyncio import create_serial_connection

    lock = asyncio.Lock()

    async def locked_coroutine(coro):
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
        
        @locked_coroutine
        async def sendCommand(self, command, args = {}):
            request = RS232_COMMANDS[command].format(**args) + EOL
            await self._protocol.send(request)
            response = await self._protocol.read()
            return self._parse_response(response)

        @locked_coroutine
        async def switch_all_on(self):
            await self.sendCommand('power_on')

        @locked_coroutine
        async def switch_all_off(self):
            await self.sendCommand('power_off')

        @locked_coroutine
        async def flash_on(self):
            await self.sendCommand('flash_on')

        @locked_coroutine
        async def flash_off(self):
            await self.sendCommand('flash_off')

        @locked_coroutine
        async def set_dimmer_level(self, zone: int, level: int, system = SYSTEM1):
            level = int(max(0, min(level, MAX_DIMMER_LEVEL)))
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            await self.sendCommand('set_dimmer_level', args = { 'zone': zone, 'level': level })

        @locked_coroutine
        async def switch_on(self, zone: int, system = SYSTEM1):
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            await self.sendCommand('switch_on', args = { 'zone': zone })

        @locked_coroutine
        async def switch_off(self, zone: int, system = SYSTEM1):
            if zone < 1 or zone > MAX_ZONES:
                raise ValueError(f"Invalid zone {zone} specified")
            await self.sendCommand('switch_off', args = { 'zone': zone })

        @locked_coroutine
        async def zone_status(self) -> dict:
            response = await self.sendCommand('zone_map_inquiry')
            if not response:
                LOG.warning(f"Failed updating RadioRA Classic zone status from {self._tty}")
                return None

            data = {}
            data[SYSTEM1] = response

            # handle multiple bridged zones
            if 'system' in response:
                response = await self._protocol.read() # read second bridged status line
                data_s2 = self._parse_response(response)
                data[SYSTEM2] = data_s2

            return self._handle_zone_status(data)

        @locked_coroutine
        async def update(self):
            await self.zone_status()
            return

        @locked_coroutine
        async def is_zone_on(self, zone: int, system = SYSTEM1):
            if not self._cached_zone_status:
                await self.update()
            return self._handle_is_zone_on(zone, system)

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

        async def read(self, request: bytes, skip=0):
            result = bytearray()

            # read response
            try:
                while True:
                    result += await asyncio.wait_for(self.q.get(), TIMEOUT, loop=self._loop)
                    if len(result) > skip and result[-LEN_EOL:] == EOL:
                        ret = bytes(result)
                        LOG.debug('Received "%s"', ret)
                        return ret.decode(ENCODING)
            except asyncio.TimeoutError:
                LOG.error("Timeout during receiving response for command '%s', received='%s'", request, result)

        async def send(self, request: bytes, skip=0):
            await self._connected.wait()

            # Only one transaction at a time
            with (await self._lock):
                # send/receive on command/response at a time, so clear out any pending
                self._transport.serial.reset_output_buffer()
                self._transport.serial.reset_input_buffer()
                while not self.q.empty():
                    self.q.get_nowait()

                # send command
                self._transport.write(request)

                # read response
                return await self.read(request)


    factory = functools.partial(RadioRAProtocolAsync, loop)
    _, protocol = await create_serial_connection(loop, factory, tty, **SERIAL_INIT_ARGS)
    return RadioRAControllerAsync(tty, protocol)