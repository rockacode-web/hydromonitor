########################################################################################################
#                                                                                                      #
#   MQTT Paho Documentation - https://eclipse.dev/paho/index.php?page=clients/python/docs/index.php    #
#                                                                                                      #
########################################################################################################
import paho.mqtt.client as mqtt
from random import randint
from json import dumps, loads


class MQTT:
    ID = f"IOT_B_{randint(1,1000000)}"

    # Hardware publishes sensor updates to: 620171712
    # Hardware listens for controls on:      620171712_sub
    sub_topics = [("620171712", 0), ("620171712_sub", 0)]

    def __init__(self, mongo):
        self.loads = loads
        self.dumps = dumps
        self.mongo = mongo

        self.client = mqtt.Client(
            client_id=self.ID,
            clean_session=True,
            reconnect_on_failure=True
        )

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe

        # Topic-specific callbacks
        self.client.message_callback_add("620171712", self.GDP)
        self.client.message_callback_add("620171712_sub", self.toggle)

        # ✅ IMPORTANT: Use the SAME broker as the ESP32
        # If your ESP32 uses "www.yanacreations.com", you can use that instead.
        self.MQTT_HOST = "84.247.187.64"
        self.MQTT_PORT = 1883

        print(f"MQTT: Connecting to broker {self.MQTT_HOST}:{self.MQTT_PORT} as {self.ID}")
        self.client.connect_async(self.MQTT_HOST, self.MQTT_PORT, 60)

        # Start networking loop so callbacks actually run
        self.client.loop_start()

    def connack_string(self, rc):
        connection = {
            0: "Connection successful",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorised",
        }
        return connection.get(rc, f"Unknown RC={rc}")

    def on_connect(self, client, userdata, flags, rc):
        print("\nMQTT:", self.connack_string(rc), " ID:", client._client_id.decode("utf-8"))
        client.subscribe(self.sub_topics)

    def on_subscribe(self, client, userdata, mid, granted_qos):
        print("MQTT: Subscribed to", [topic[0] for topic in self.sub_topics])

    def publish(self, topic, payload):
        try:
            info = self.client.publish(topic, payload)
            info.wait_for_publish()
            return info.is_published()
        except Exception as e:
            print(f"MQTT: Publish failed {str(e)}")
            return False

    def on_message(self, client, userdata, msg):
        # Fallback handler (only runs for topics without message_callback_add)
        try:
            print("MQTT (generic):", msg.topic, msg.payload.decode("utf-8"))
        except Exception as e:
            print(f"MQTT: onMessage Error: {str(e)}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            print("MQTT: Unexpected Disconnection.")

    # =========================================================
    # CALLBACK 1: Sensor updates from hardware -> insert DB
    # =========================================================
    def GDP(self, client, userdata, msg):
        """
        Expected payload schema:
        {"id":"620171712","timestamp":1702212234,"temperature":30,"humidity":90,"heatindex":30}
        """
        try:
            payload = msg.payload.decode("utf-8")
            data = self.loads(payload)

            # Ensure timestamp is an int (unique index depends on this)
            if "timestamp" in data:
                data["timestamp"] = int(data["timestamp"])

            print(f"MQTT: Sensor msg received on {msg.topic} -> {data}")

            ok = self.mongo.addUpdate(data)

            if ok:
                print("MQTT: ✅ Inserted into MongoDB climo")
            else:
                print("MQTT: ⚠️ DB insert returned False (possibly duplicate timestamp)")

        except Exception as e:
            # If your unique index blocks duplicates, pymongo usually raises DuplicateKeyError here
            print(f"MQTT: GDP Error - {str(e)}")

    # =========================================================
    # CALLBACK 2: Controls messages -> log / optional forward
    # =========================================================
    def toggle(self, client, userdata, msg):
        try:
            payload = msg.payload.decode("utf-8")
            data = self.loads(payload)
            print("MQTT: Controls message:", data)
        except Exception as e:
            print(f"MQTT: toggle Error - {str(e)}")
