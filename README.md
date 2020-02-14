# Python interface for Lutron RadioRA Classic RS232 bridge


## Usage

For Monoprice and Dayton Audio 6-zone amplifiers:

```python
import pyradiora.classic

radiora = get_sync_radiora_controller('/dev/ttyUSB0')

radiora.turn_all_on()
radiora.turn_on(zone_id)
radiora.set_dimmer_level(zone_id, level)

radiora.flash_on()
radiora.flash_off()
```

## See Also

* [Home Assistant integration](https://www.home-assistant.io/integrations/monoprice/)
