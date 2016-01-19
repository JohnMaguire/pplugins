import time
import logging
import Queue

from pplugins import Plugin

class ExamplePlugin(Plugin):
    """Don't do anything special"""

    def __init__(self, *args, **kwargs):
        self.logger = logging.getLogger(__name__)

        super(ExamplePlugin, self).__init__(*args, **kwargs)

    def run(self):
        self.logger.info("Child, started!")

        while True:
            try:
                event = self.interface.get_event(block=False)
            except Queue.Empty:
                self.logger.info("Child, no message. Waiting .1 second")
                time.sleep(.1)
                continue

            if event is None:
                self.logger.info("Child, exiting.")
                break
