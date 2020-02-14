# Python interface for Lutron RadioRA Classic RS232 bridge

## Usage

#### Synchronous

```python
import pyradiora.classic

radiora = get_radiora_controller('/dev/ttyUSB0')

radiora.turn_all_on()
radiora.turn_on(zone_id)
radiora.set_dimmer_level(zone_id, level)

radiora.flash_on()
radiora.flash_off()

if radiora.is_on(zone_id):
   radiora.turn_off(zone_id)
```

#### Asynchronous

With the `asyncio` version, all methods of the RadioRA Classic controller are coroutines:

```python
import asyncio
from pyradiora.classic import get_async_radiora_controller

async def main(loop):
      radiora = await get_async_radiora_controller('/dev/ttyUSB0', loop)
      await radiora.turn_on(zone_id)

loop = asyncio.get_event_loop()
loop.run_until_complete(main(loop))
```

## See Also

* [Home Assistant integration](https://www.home-assistant.io/integrations/monoprice/)
