import time
import Queue

from pplugins import Plugin


class ExamplePlugin(Plugin):
    """Don't do anything special"""

    def run(self):
        print("Child, started!")

        while True:
            try:
                event = self.interface.get_event(block=False)
            except Queue.Empty:
                print("Child, no message. Waiting 1 second")
                time.sleep(1)
                continue

            if event is None:
                print("Child, exiting.")
                break
