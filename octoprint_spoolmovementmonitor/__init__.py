# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.events import Events
import RPi.GPIO as GPIO
from datetime import date
import datetime
import time
from time import sleep
# from flask import jsonify
import octoprint.util

class SpoolmovementmonitorPlugin(octoprint.plugin.StartupPlugin,
                                 octoprint.plugin.EventHandlerPlugin,
                                 octoprint.plugin.TemplatePlugin,
                                 octoprint.plugin.SettingsPlugin,
                                 octoprint.plugin.BlueprintPlugin):

    light_toggle = False
    stopped_triggered = False
    monitor_active = False
    
    def __init__(self):
        self.timer1 = None  # timer for when print should pause
        self.timer2 = None  # timer for indicator2 LED - flashes faster as runout time approaches
        self.target_time = 0  # epoch seconds for when print should pause                                 

    def on_after_startup(self):
        self._logger.info("Spool Movement Monitor %s started", self._plugin_version)

    ##~~ SettingsPlugin mixin

    def _setup_sensor(self):
        self._logger.debug("Starting _setup_sensor")
        if self.movement_monitor_enabled():
            self._logger.debug("Spool movement monitor enabled...")
            if self.mode == 0:
                self._logger.debug("Using Board Mode")
                GPIO.setmode(GPIO.BOARD)

            else:
                self._logger.debug("Using BCM Mode")
                GPIO.setmode(GPIO.BCM)

            GPIO.setup(self.input_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self.indicator1_pin, GPIO.OUT)
            GPIO.setup(self.indicator2_pin, GPIO.OUT)
            GPIO.setup(self.indicator3_pin, GPIO.OUT)
            GPIO.setup(self.indicator4_pin, GPIO.OUT)            
            GPIO.output(self.indicator1_pin, False)   
            GPIO.output(self.indicator2_pin, False)
            GPIO.output(self.indicator3_pin, False)
            GPIO.output(self.indicator4_pin, False)
            GPIO.remove_event_detect(self.input_pin)
            GPIO.add_event_detect(
                self.input_pin, GPIO.BOTH,
                callback=self.movement_sensor_callback,
                bouncetime=self.input_bounce)
            self._logger.info("Spool movement monitor set up on GPIO Pin [%s]" % self.input_pin)

        else:
            self._logger.info("No input configured, not active")

    def on_after_startup(self):
        if self.mode == 0:
            # self._logger.debug("Using Board Mode")
            GPIO.setmode(GPIO.BOARD)

        else:
            # self._logger.debug("Using BCM Mode")
            GPIO.setmode(GPIO.BCM)

        self._logger.debug("Time is [%s]" % int(time.time()))
        self._setup_sensor()
        self._logger.debug("Spool movement monitoring active on GPIO Pin [%s]" % self.input_pin)
        GPIO.remove_event_detect(self.input_pin)
        GPIO.add_event_detect(
            self.input_pin, GPIO.BOTH,
            callback=self.movement_sensor_callback,
            bouncetime=self.input_bounce
        )

    def movement_monitor_enabled(self):
        return self.input_pin != -1

    def indicator1_enabled(self):
        return self.indicator1_pin != -1

    def indicator2_enabled(self):
        return self.indicator2_pin != -1

    def indicator3_enabled(self):
        return self.indicator3_pin != -1

    def indicator4_enabled(self):
        return self.indicator4_pin != -1

    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=False)]

    def on_event(self, event, payload):
        self._logger.debug("Event [%s]" % event)
        if event in (
            Events.PRINT_STARTED,
            Events.PRINT_RESUMED
        ):
            self._logger.info(
                "%s: Setting monitoring active " % (event))
            self.monitor_active = True
#            GPIO.remove_event_detect(self.input_pin)
#            GPIO.add_event_detect(
#                self.input_pin, GPIO.BOTH,
#                callback=self.movement_sensor_callback,
#                bouncetime=self.input_bounce)
            GPIO.output(self.indicator3_pin, True)    
            self.start_timer1()
            self.start_timer2()                        
        elif event in (
            Events.PRINT_DONE,
            Events.PRINT_FAILED,
            Events.PRINT_CANCELLED,
            Events.ERROR
        ):
            self._logger.info("%s: Setting monitoring inactive " % (event))
#            GPIO.output(self.indicator3_pin, False)               
#            if self.monitor_active:
#                GPIO.remove_event_detect(self.input_pin)
            GPIO.output(self.indicator3_pin, False)     
            GPIO.output(self.indicator2_pin, False)           
            self.monitor_active = False
            self.timer1.cancel()
            self.timer2.cancel()

    def movement_sensor_callback(self, _):
        sleep(self.input_bounce/1000)
        self._logger.info("Movement sensor callback triggered")
#        self._logger.debug("Input value is %s" % str(GPIO.input(self.input_pin)))
#        self._logger.debug(self.indicator1_pin)
        GPIO.output(self.indicator1_pin, GPIO.input(self.input_pin))
        self.target_time = int(time.time()) + self.timeout_seconds
#        GPIO.output(self.indicator2_pin, self.light_toggle)
#        self.light_toggle = not self.light_toggle
        if self.monitor_active:
#           self.cancel_timer1()
            self.start_timer1()
#           self.cancel_timer2()
            self.start_timer2()

    def run_timer1_tasks(self):  # Cancels the print
        self._logger.info("Timed out! Cancelling the print!")
        self.stopped_pause_print = True
        GPIO.output(self.indicator3_pin, False)
        GPIO.output(self.indicator4_pin, True)                   
        self._printer.pause_print()
#        self.start_timer1()

    def start_timer1(self):
        if self.timer1:
            self._logger.debug("Main timer active, restarting")
            self.timer1.cancel()

        self.target_time = int(time.time()) + self.timeout_seconds  # epoch seconds for when print should pause
        self._logger.debug("Starting main timer - target time is [%s]" % datetime.datetime.fromtimestamp(self.target_time))
        interval = self.timeout_seconds
#        interval = 6.0
        self.timer1 = octoprint.util.ResettableTimer(
            interval, self.run_timer1_tasks
        )
        self.timer1.start()
#        self.timer2.start()        
#        GPIO.output(self.indicator3_pin, True)

    def cancel_timer1(self):
        if self.timer1:
            self._logger.debug("Cancelling timer1")
            self.timer1.cancel()
#        GPIO.output(self.indicator3_pin, False)            

    def run_timer2_tasks(self):  # Blinks indicator2 LED - faster as target time gets closer
        self._logger.debug("Running blink timer")
        #GPIO.output(self.indicator1_pin, self.light_toggle)
#        self.light_toggle = not self.indicator2_pin
#        GPIO.output(self.indicator2_pin, self.light_toggle)
#       self._logger.debug("Input value is %s" % str(GPIO.input(self.input_pin)))
        GPIO.output(self.indicator1_pin, GPIO.input(self.input_pin))
#        self.light_toggle = not self.light_toggle
        self.start_timer2()
        #GPIO.output(self.indicator1_pin, GPIO.input(self.input_pin))  # Set led1 to same as input1 in case it's different

    def start_timer2(self):
        interval = ((self.target_time - int(time.time())) / 20) + 0.1
        if self.target_time > int(time.time()):
            self._logger.debug("OK, target time is in future")
        else:
            self._logger.debug("Target time is in the past, not starting timer2")
            return

        self._logger.debug("Starting blink timer - interval is %s" % str(interval))
#        interval = 10.0
        if self.timer2:
            self._logger.debug("Blink timer was active - restarting")
            self.timer2.cancel()

        self.light_toggle = not self.light_toggle
        GPIO.output(self.indicator2_pin, self.light_toggle)
        self._logger.debug("Light toggle is now %s" % str(self.light_toggle))        
        self.timer2 = octoprint.util.ResettableTimer(
            interval, self.run_timer2_tasks
        )
        self.timer2.start()

    def cancel_timer2(self):
        if self.timer2:
            self._logger.debug("Cancelling blink timer")
            self.timer2.cancel()

    def on_settings_save(self, data):
        self._logger.debug("Saving settings")
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)        

    def get_settings_defaults(self):
        return dict(
            mode=0,    # Board mode
            input_pin=-1,   # Default is no pin
            input_bounce=100,  # Debounce 100ms
            timeout_seconds=120,  # seconds
            no_filament_gcode='',  #
            stopped_pause_print=False,  # Debounce 250ms
            indicator1_pin=-1,  # Disabled
            indicator2_pin=-1,  # Disabled
            indicator3_pin=-1,  # Disabled
            indicator4_pin=-1,  # Disabled            
            send_gcode_only_once=False,  # Default set to False for backward compatibility
        )

    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/spoolmovementmonitor.js"],
            "css": ["css/spoolmovementmonitor.css"],
            "less": ["less/spoolmovementmonitor.less"]
        }

    @property
    def mode(self):
        return int(self._settings.get(["mode"]))

    @property
    def input_pin(self):
        return int(self._settings.get(["input_pin"]))

    @property
    def input_bounce(self):
        return int(self._settings.get(["input_bounce"]))

    @property
    def timeout_seconds(self):
        return int(self._settings.get(["timeout_seconds"]))

    @property
    def no_filament_gcode(self):
        return str(self._settings.get(["no_filament_gcode"])).splitlines()

    @property
    def stopped_pause_print(self):
        return self._settings.get_boolean(["stopped_pause_print"])

    @property
    def indicator1_pin(self):
        return int(self._settings.get(["indicator1_pin"]))

    @property
    def indicator2_pin(self):
        return int(self._settings.get(["indicator2_pin"]))

    @property
    def indicator3_pin(self):
        return int(self._settings.get(["indicator3_pin"]))

    @property
    def indicator4_pin(self):
        return int(self._settings.get(["indicator4_pin"]))

    @property
    def send_gcode_only_once(self):
        return self._settings.get_boolean(["send_gcode_only_once"])

    ##~~ Softwareupdate hook

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "spoolmovementmonitor": {
                "displayName": "Spoolmovementmonitor Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "jaxxfrost",
                "repo": "OctoPrint-SpoolMovementMonitor",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/jaxxfrost/OctoPrint-SpoolMovementMonitor/archive/{target_version}.zip",
            }
        }


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Spoolmovementmonitor Plugin"

# Starting with OctoPrint 1.4.0 OctoPrint will also support to run under Python 3 in addition to the deprecated
# Python 2. New plugins should make sure to run under both versions for now. Uncomment one of the following
# compatibility flags according to what Python versions your plugin supports!
#__plugin_pythoncompat__ = ">=2.7,<3" # only python 2
__plugin_pythoncompat__ = ">=3,<4" # only python 3
#__plugin_pythoncompat__ = ">=2.7,<4" # python 2 and 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = SpoolmovementmonitorPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
