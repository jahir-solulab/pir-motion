import logging
import json
from threading import Timer, Thread
from subprocess import check_output, call
from gpiozero import MotionSensor
from signal import pause
import paho.mqtt.client as mqtt
import time
import uuid

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

    def __init__(self, gpio_pin, display_delay, verbose, mqtt_broker, mqtt_port, mqtt_topic_pub, mqtt_topic_toggle):
        if verbose == True:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

        logging.info("[Motion]: Initializing - GPIO_PIN: %s, DISPLAY_DELAY: %s, VERBOSE: %s" % (gpio_pin, display_delay, verbose))

        self.display_delay = display_delay
        self.pir = MotionSensor(gpio_pin)
        self.pir.when_motion = self.onMotion
        self.resetTimer()

        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic_pub = mqtt_topic_pub
        self.mqtt_topic_toggle = mqtt_topic_toggle

        # Generate device ID from MAC address and save it to a file
        mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0, 2 * 6, 2)])
        device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, mac_address))
        self.save_device_id(device_id)

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect

        self.connect_to_mqtt()

        pause()

    def connect_to_mqtt(self):
        while True:
            try:
                logging.info("[Motion]: Connecting to MQTT broker...")
                self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
                break
            except Exception as e:
                logging.error("[Motion]: MQTT connection failed. Retrying in 5 seconds...")
                time.sleep(5)

    def save_device_id(self, device_id):
        try:
            with open("device_id.txt", "w") as f:
                f.write(device_id)
            logging.info("[Motion]: Device ID saved to file")
        except Exception as e:
            logging.error("[Motion]: Error saving device ID to file: %s" % str(e))

    def load_device_id(self):
        try:
            with open("device_id.txt", "r") as f:
                device_id = f.read().strip()
                logging.info("[Motion]: Device ID loaded from file")
                return device_id
        except Exception as e:
            logging.error("[Motion]: Error loading device ID from file: %s" % str(e))
            return None

    def on_connect(self, client, userdata, flags, rc):
        logging.info("[Motion]: Connected to MQTT broker with result code " + str(rc))
        self.mqtt_client.subscribe(self.mqtt_topic_toggle)

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logging.warning("[Motion]: Unexpected disconnection from MQTT broker. Attempting to reconnect...")
            self.connect_to_mqtt()

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
            
        # Check if the device ID is available
        device_id = self.load_device_id()
        if device_id is not None:
            # Construct JSON payload
            payload = {
                "device_id": device_id,
                "status": "on"
            }
            # Publish payload to the specified MQTT topic
            self.mqtt_client.publish(self.mqtt_topic_pub, json.dumps(payload))
        
        self.resetTimer()

    def on_toggle_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
            device_id = payload.get("device_id")
            status = payload.get("status")

            if device_id == self.load_device_id():
                if status == "off":
                    self.timer.cancel()
                    Display.turnOff()
                elif status == "on":
                    self.resetTimer()
                    Display.turnOn()
                else:
                    logging.warning("[Motion]: Invalid status received: %s" % status)
        except Exception as e:
            logging.error("[Motion]: Error processing toggle message: %s" % str(e))

# MQTT configurations
MQTT_BROKER = "18.222.69.128"
MQTT_PORT = 1883
MQTT_TOPIC_PUB = "motion_detection"
MQTT_TOPIC_TOGGLE = "toggle_motion_sensor"

motion = Motion(gpio_pin=4, display_delay=60, verbose=False, mqtt_broker=MQTT_BROKER, mqtt_port=MQTT_PORT, mqtt_topic_pub=MQTT_TOPIC_PUB, mqtt_topic_toggle=MQTT_TOPIC_TOGGLE)

