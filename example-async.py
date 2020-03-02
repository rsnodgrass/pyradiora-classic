#! /usr/local/bin/python3

import time
import asyncio
import argparse
from pyradiora_classic import get_async_radiora_controller

parser = argparse.ArgumentParser(description='RadioRA Classic client example')
parser.add_argument('--tty', help='/dev/tty to use (e.g. /dev/tty.usbserial-A501SGSZ)', required=True)
args = parser.parse_args()

async def main():
    radiora = await get_async_radiora_controller(args.tty, asyncio.get_event_loop())

    print(f"RadioRA RS232 controller version = {await radiora.sendCommand('version')}")
    print(radiora.zone_status())

asyncio.run(main())
