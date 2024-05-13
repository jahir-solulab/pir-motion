import logging
import json
import uuid
import os
import time
from threading import Timer, Thread
from subprocess import check_output, call
from gpiozero import MotionSensor
import paho.mqtt.client as mqtt

class Display:
    @staticmethod
    def getDisplayStatus():
        status = check_output(["vcgencmd", "display_power"])
        isTurnedOn = status == "display_power=1"
        logging.debug("[Display]: Is turned on: %s" % isTurnedOn)
        if isTurnedOn:
            logging.debug("[Display]: Status: on, display_power = 1")
        else:
            logging.debug("[Display]: Status: off")
        return isTurnedOn, status

class Motion:
    def __init__(self, gpio_pin, display_delay, verbose, mqtt_broker, mqtt_port, mqtt_topic_sub, mqtt_topic_pub, mqtt_topic_toggle):
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        logging.info("[Motion]: Initializing - GPIO_PIN: %s, DISPLAY_DELAY: %s, VERBOSE: %s" % (gpio_pin, display_delay, verbose))

        self.display_delay = display_delay
        self.pir = MotionSensor(gpio_pin)
        self.pir.when_motion = self.onMotion
        self.resetTimer()

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.connect(mqtt_broker, mqtt_port, 60)
        self.mqtt_topic_sub = mqtt_topic_sub
        self.mqtt_topic_pub = mqtt_topic_pub
        self.mqtt_topic_toggle = mqtt_topic_toggle
        self.mqtt_client.subscribe(self.mqtt_topic_sub)
        self.device_id = self.get_or_generate_device_id()
        
    def get_or_generate_device_id(self):
        id_file = 'device_id.txt'
        if os.path.isfile(id_file):
            with open(id_file, 'r') as file:
                device_id = file.read().strip()
            logging.debug("[Motion]: Retrieved device ID from file: %s" % device_id)
            return device_id
        else:
            mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)])
            device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, mac_address))
            with open(id_file, 'w') as file:
                file.write(device_id)
            logging.debug("[Motion]: Generated and saved new device ID: %s" % device_id)
            return device_id

    def resetTimer(self):
        logging.debug("[Motion]: Resetting timer..")

        if hasattr(self, 'timer') and self.timer:
            logging.debug("[Motion]: Old timer found! Destroying it!")
            self.timer.cancel()

        logging.debug("[Motion]: Setting timer for %s" % self.display_delay)
        self.timer = Timer(self.display_delay, self.turnOffDisplay)
        self.timer.start()

    def onMotion(self):
        logging.debug("[Motion]: Motion detected!")

        if not Display.getDisplayStatus()[0]:
            logging.debug("[Motion]: Display is off, turning it on!")
            self.turnOnDisplay()
            
        # Check if both user_id and device_id are available
        if hasattr(self, 'user_id') and self.user_id is not None:
            # Construct JSON payload
            payload = {
                "_user": self.user_id,
                "deviceId": self.device_id
            }
            # Publish payload to the specified MQTT topic
            self.mqtt_client.publish(self.mqtt_topic_pub, json.dumps(payload))
        
        self.resetTimer()
    
    def on_message(self, client, userdata, message):
        # Decode the message payload
        payload = json.loads(message.payload.decode())
        
        # Extract user_id and device_id
        if '_user' in payload and 'deviceId' in payload:
            self.user_id = payload['_user']
            self.device_id = payload['deviceId']
            logging.debug("[Motion]: User ID and Device ID received: %s, %s" % (self.user_id, self.device_id))
    
    def turnOnDisplay(self):
        logging.debug("[Motion]: Turning ON the display..")
        call(['vcgencmd', 'display_power', '1'])
        logging.debug("[Motion]: Status: on, display_power = 1")

    def turnOffDisplay(self):
        logging.debug("[Motion]: Turning OFF the display..")
        call(['vcgencmd', 'display_power', '0'])
        logging.debug("[Motion]: Status: off")

    def toggleSensor(self, status):
        if status.lower() == 'off':
            self.pir.when_motion = None
            logging.debug("[Motion]: Sensor turned off.")
        elif status.lower() == 'on':
            self.pir.when_motion = self.onMotion
            logging.debug("[Motion]: Sensor turned on.")
        else:
            logging.warning("[Motion]: Invalid status. Please use 'on' or 'off'.")
    
    def toggleDisplayStatus(self, status):
        if status.lower() == 'off':
            self.turnOffDisplay()
        elif status.lower() == 'on':
            self.turnOnDisplay()
        else:
            logging.warning("[Motion]: Invalid status. Please use 'on' or 'off'.")

# MQTT configurations
MQTT_BROKER = "18.222.69.128"
MQTT_PORT = 1883
MQTT_TOPIC_SUB = "toggle_device_status"
MQTT_TOPIC_PUB = "motion_detection"
MQTT_TOPIC_TOGGLE = "toggle_motion_sensor"

motion = Motion(gpio_pin=4, display_delay=60, verbose=True, mqtt_broker=MQTT_BROKER, mqtt_port=MQTT_PORT, mqtt_topic_sub=MQTT_TOPIC_SUB, mqtt_topic_pub=MQTT_TOPIC_PUB, mqtt_topic_toggle=MQTT_TOPIC_TOGGLE)

def on_toggle_message(client, userdata, message):
    payload = json.loads(message.payload.decode())
    if 'status' in payload:
        status = payload['status']
        logging.debug("[Motion]: Received status from toggle_motion_sensor: %s" % status)
        motion.toggleSensor(status)

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_toggle_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.subscribe(MQTT_TOPIC_TOGGLE)

mqtt_client.loop_forever()

