# Python interface for Lutron RadioRA Classic RS232 bridge


## Usage

For Monoprice and Dayton Audio 6-zone amplifiers:

```python
from pyra import RadioRA

radiora = PyRadioRA('/dev/ttyUSB0')

lights = radiora.lights

# FIXME: lights, dimmers, current status
```

## See Also

* [Home Assistant integration](https://www.home-assistant.io/integrations/monoprice/)
