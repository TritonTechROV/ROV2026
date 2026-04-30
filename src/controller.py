# controller #
import logging, json

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Controller:

    # controller input mapping
    @staticmethod
    def load_config():
        with open("src/config/xbox.json") as f:
            return json.load(f)

    # default to empty list
    def __init__(self, buttons=None, axes=None):
        self._buttons = buttons or []
        self._axes = axes or []

        config = self.load_config()

        BUTTON_NAMES = config["button"]
        AXIS_NAMES = config["axis"]

        self.BUTTON_INDEX = {b: i for i, b in enumerate(BUTTON_NAMES)}
        self.AXIS_INDEX = {a: i for i, a in enumerate(AXIS_NAMES)}

    # print debug hook
    def print_state(self):
        print("Buttons:", self._buttons)
        print("Axes:", self._axes)

    # idx + name access for buttons
    def button(self, key):
        if isinstance(key, str):
            return self._buttons[self.BUTTON_INDEX[key]]
        return self._buttons[key]

    # idx + name access for axes
    def axis(self, key):
        if isinstance(key, str):
            return self._axes[self.AXIS_INDEX[key]]
        return self._axes[key]

    # direct list-like access
    @property
    def buttons(self):
        return self._buttons

    # setter for print debugging
    @buttons.setter
    def buttons(self, value):
        self._buttons = value or []
        self.print_state()

    @property
    def axes(self):
        return self._axes

    @axes.setter
    def axes(self, value):
        self._axes = value or []
        self.print_state()
