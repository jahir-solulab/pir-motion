#!/usr/bin/python

import logging
from threading import Timer
from subprocess import check_output, call
from gpiozero import MotionSensor
from signal import pause
import paho.mqtt.client as mqtt

class Display:
    @staticmethod
    def isTurnedOn():
        status = check_output(["vcgencmd", "display_power"])
        isTurnedOn = status == "display_power=1"
        logging.debug("[Display]: Is turned on: %s" % isTurnedOn)
        return isTurnedOn

    @staticmethod
    def turnOn():
        logging.debug("[Display]: Turning ON the display..")
        call(['vcgencmd', 'display_power', '1'])

    @staticmethod
    def turnOff():
        logging.debug("[Display]: Turning OFF the display..")
        call(['vcgencmd', 'display_power', '0'])

class Motion:
    timer = None

    def __init__(self, gpio_pin, display_delay, verbose, mqtt_broker, mqtt_port, mqtt_topic):
        if verbose == True:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        logging.info("[Motion]: Initializing - GPIO_PIN: %s, DISPLAY_DELAY: %s, VERBOSE: %s" % (gpio_pin, display_delay, verbose))

        if verbose == True:
            logging.basicConfig(level=logging.DEBUG)

        self.display_delay = display_delay
        self.pir = MotionSensor(gpio_pin)
        self.pir.when_motion = self.onMotion
        self.resetTimer()
        
        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(mqtt_broker, mqtt_port, 60)
        
        pause()

    def resetTimer(self):
        logging.debug("[Motion]: Resetting timer..")

        if self.timer:
            logging.debug("[Motion]: Old timer found! Destroying it!")
            self.timer.cancel()

        logging.debug("[Motion]: Setting timer for %s" % self.display_delay)
        self.timer = Timer(self.display_delay, Display.turnOff)
        self.timer.start()

    def onMotion(self):
        logging.debug("[Motion]: Motion detected!")

        if Display.isTurnedOn() == False:
            logging.debug("[Motion]: Display is off, turning it on!")
            Display.turnOn()
            
        # Publish motion detection status to MQTT broker
        self.mqtt_client.publish(mqtt_topic, "Motion Detected")
        
        self.resetTimer()

# MQTT configurations
MQTT_BROKER = "18.222.69.128"
MQTT_PORT = 1883
MQTT_TOPIC = "motion_detection"

motion = Motion(gpio_pin=4, display_delay=60, verbose=False, mqtt_broker=MQTT_BROKER, mqtt_port=MQTT_PORT, mqtt_topic=MQTT_TOPIC)
