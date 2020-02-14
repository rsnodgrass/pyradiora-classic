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

```python
import pyradiora.classic

radiora = get_async_radiora_controller('/dev/ttyUSB0', event_loop)
radiora.turn_on(zone_id)
```

## See Also

* [Home Assistant integration](https://www.home-assistant.io/integrations/monoprice/)
