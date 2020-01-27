# IKEA Tradfri Plugin - Pycoap version
#
# Author: Moroen
#
"""
<plugin key="IKEA-Tradfri" name="IKEA Tradfri Plugin - version 0.8.1" author="moroen" version="0.8.1" wikilink="http://www.domoticz.com/wiki/plugins/plugin.html" externallink="https://www.google.com/">
    <description>
        <h2>IKEA Tradfri</h2><br/>
    </description>
    <params>
        <param field="Mode1" label="Add groups as devices" width="75px">
            <options>
                <option label="Yes" value="True"/>
                <option label="No" value="False"  default="true" />
            </options>
        </param>
        <param field="Mode2" label="Observe changes" width="75px">
            <options>
                <option label="Yes" value="True"/>
                <option label="No" value="False"  default="true" />
            </options>
        </param>
        <param field="Mode3" label="Polling interval (seconds)" width="75px" required="true" default="300"/>
        <param field="Mode4" label="Transition time (tenth of a second)" width="75px" required="false" default="10"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
import os
import json
import site
import sys
import threading
import time
import datetime

# Get full import PATH
site.main()

_globalError = None

# Need to set config before import from module
try:
    from tradfricoap.config import get_config, host_config
    from tradfricoap import ApiNotFoundError
    
    CONFIGFILE = "{}/config.json".format(os.path.dirname(os.path.realpath(__file__)))
    CONF = get_config(CONFIGFILE)

    if CONF["Api"] == "Coapcmd":
        from tradfricoap.coapcmd_api import set_coapcmd
        set_coapcmd("{}/bin/coapcmd".format(os.path.dirname(os.path.realpath(__file__))))

except ImportError:
    _globalError="Module 'tradfricoap' not found"

if __name__ == "__main__":
    from cli import get_args
    
    # from tradfri.config import host_config

    args = get_args()
    if args.command == "api":
        config = host_config(CONFIGFILE)
        config.set_config_item("api", args.API)
        config.save()
        exit()

    try:
        from tradfricoap.device import get_devices, get_device
        from tradfricoap.gateway import create_ident
        from tradfricoap.errors import HandshakeError
        
    except ImportError:
        print("Module 'tradfricoap' not found!")
        exit()

    except ApiNotFoundError as e:
        if e.api == "pycoap":
            print('Py3coap module not found!\nInstall with "pip3 install py3coap" or select another api with "python3 plugin.py api"')
        elif e.api == "coapcmd":
            print( 'coapcmd  not found!\nInstall with "bash install_coapcmd.sh" or select another api with "python3 plugin.py api"')
        exit()

    if args.command == "raw":
        dev = get_device(args.ID)
        print(dev.Raw)
        
    if args.command == "list":
        try:
            devices = get_devices(args.groups)
        except HandshakeError:
            print("Connection timed out")
            exit()

        except ApiNotFoundError as e:
            print(e.message)
            exit()

        if devices is None:
            print("Unable to get list of devices")
        else:
            lights = []
            plugs = []
            blinds = []
            groups = []
            others = []

            for dev in devices:
                if dev.Type == "Light":
                    lights.append(dev.Description)
                elif dev.Type == "Plug":
                    plugs.append(dev.Description)
                elif dev.Type == "Blind":
                    blinds.append(dev.Description)
                elif dev.Type == "Group":
                    groups.append(dev.Description)
                else:
                    others.append(dev.Description)

            if len(lights):
                print("Lights:")
                print("\n".join(lights))

            if len(plugs):
                print("\nPlugs:")
                print("\n".join(plugs))

            if len(blinds):
                print("\nBlinds:")
                print("\n".join(blinds))

            if len(groups):
                print("\nGroups:")
                print("\n".join(groups))

            if len(others):
                print("\nOthers:")
                print("\n".join(others))

    elif args.command == "config":
        try:
            create_ident(args.IP, args.KEY, CONFIGFILE)
        except HandshakeError:
            print("Connection timed out")


    exit()


## Domoticz Plugin
import Domoticz

try:
    from tradfricoap.device import get_device, get_devices, set_transition_time
    from tradfricoap.errors import (
        HandshakeError,
        UriNotFoundError,
        ReadTimeoutError,
        WriteTimeoutError,
        set_debug_level,
    )
    from tradfricoap.colors import WhiteOptions, colorOptions
except ImportError:
    _globalError="Unable to find tradfricoap"
except SystemExit:
    _globalError="Unable to initialize tradfricoap"
except ApiNotFoundError as e:
    _globalError=e.message

class BasePlugin:
    enabled = False

    lights = {}

    lastPollTime = None
    pollInterval = None

    hasTimedOut = False
    devicesMoving = []
    commandQueue = []

    def __init__(self):
        # self.var = 123
        return

    def indexRegisteredDevices(self):
        if len(Devices) > 0:
            # Some devices are already defined
            try:
                for aUnit in Devices:
                    dev_id = Devices[aUnit].DeviceID.split(":")
                    self.updateDevice(aUnit, dev_id[0])

                return [dev.DeviceID for key, dev in Devices.items()]

            except (HandshakeError, ReadTimeoutError, WriteTimeoutError):
                self.hasTimedOut = True
                return
            else:
                self.hasTimedOut = False
                raise
        else:
            deviceID = [-1]
            return deviceID

    def updateDevice(self, Unit, device_id=None, override_level=None):
        # Domoticz.Debug("Updating device {} - Switchtype {}".format(device_id, Devices[Unit].SwitchType))
        deviceUpdated = False
        try:
            if device_id is not None:
                self.lights[Unit] = get_device(id=device_id)
            else:
                self.lights[Unit].Update()

            if self.lights[Unit].State is None:
                # Illegal Device
                return

            if Devices[Unit].SwitchType == 0:
                # On/off - device
                if (Devices[Unit].nValue != self.lights[Unit].State) or (
                    Devices[Unit].sValue != str(self.lights[Unit].Level)
                ):
                    Devices[Unit].Update(
                        nValue=self.lights[Unit].State,
                        sValue=str(self.lights[Unit].Level),
                    )

            elif Devices[Unit].SwitchType == 7:
                # Dimmer
                if self.lights[Unit].Level is not None:
                    if override_level is None:
                        level = str(int(100 * (int(self.lights[Unit].Level) / 255)))
                    else:
                        level = override_level

                    if (Devices[Unit].nValue != self.lights[Unit].State) or (
                        Devices[Unit].sValue != str(level)
                    ):
                        Devices[Unit].Update(
                            nValue=self.lights[Unit].State, sValue=str(level)
                        )

            elif Devices[Unit].SwitchType == 13:
                if (Devices[Unit].nValue != self.lights[Unit].State) or (
                    Devices[Unit].sValue != str(self.lights[Unit].Level)
                ):
                    Devices[Unit].Update(
                        nValue=self.lights[Unit].State,
                        sValue=str(self.lights[Unit].Level),
                    )
                    deviceUpdated = True

            if (
                Devices[Unit].DeviceID[-3:] == ":WS"
                or Devices[Unit].DeviceID[-4:] == ":CWS"
            ):
                if (Devices[Unit].nValue != self.lights[Unit].State) or (
                    Devices[Unit].sValue != str(self.lights[Unit].Color_level)
                ):
                    Devices[Unit].Update(
                        nValue=self.lights[Unit].State,
                        sValue=str(self.lights[Unit].Color_level),
                    )
            
            self.hasTimedOut = False
            return deviceUpdated

        except (HandshakeError, ReadTimeoutError, WriteTimeoutError):
            Domoticz.Debug(
                "Error updating device {}: Connection time out".format(device_id)
            )
            self.hasTimedOut = True
            raise            

    def registerDevices(self):
        unitIds = self.indexRegisteredDevices()
        if self.hasTimedOut:
            return

        ikeaIds = []

        # Add unregistred lights
        try:
            if Parameters["Mode1"] == "True":
                tradfriDevices = get_devices(groups=True)
            else:
                tradfriDevices = get_devices()

            if tradfriDevices == None:
                Domoticz.Log("Failed to get Tradfri-devices")
                return

            for aLight in tradfriDevices:
                devID = str(aLight.DeviceID)
                ikeaIds.append(devID)

                if not devID in unitIds:
                    Domoticz.Debug(
                        "Processing: {0} - {1}".format(aLight.Description, aLight.Type)
                    )
                    new_unit_id = firstFree()

                    if aLight.Type == "Plug":
                        Domoticz.Device(
                            Name=aLight.Name,
                            Unit=new_unit_id,
                            Type=244,
                            Subtype=73,
                            Switchtype=0,
                            Image=1,
                            DeviceID=devID,
                        ).Create()
                        self.updateDevice(new_unit_id, devID)

                    if aLight.Type == "Remote":
                        Domoticz.Device(
                            Name=aLight.Name + " - Battery level",
                            Unit=new_unit_id,
                            Type=243,
                            Subtype=6,
                            DeviceID=devID,
                        ).Create()

                    if aLight.Type == "Blind":
                        deviceType = 244
                        subType = 73
                        switchType = 13

                        Domoticz.Device(
                            Name=aLight.Name,
                            Unit=new_unit_id,
                            Type=deviceType,
                            Subtype=subType,
                            Switchtype=switchType,
                            DeviceID=devID,
                        ).Create()
                        self.updateDevice(new_unit_id, devID)

                    if aLight.Type == "Light" or aLight.Type == "Group":
                        deviceType = 244
                        subType = 73
                        switchType = 7

                        # Basic device
                        Domoticz.Device(
                            Name=aLight.Name,
                            Unit=new_unit_id,
                            Type=deviceType,
                            Subtype=subType,
                            Switchtype=switchType,
                            DeviceID=devID,
                        ).Create()
                        self.updateDevice(new_unit_id, devID)
                        if aLight.Color_space == "W":
                            continue

                if aLight.Color_space == "CWS" and devID + ":CWS" not in unitIds:
                    new_unit_id = firstFree()
                    Domoticz.Debug("Registering: {0}:CWS".format(aLight.DeviceID))
                    Domoticz.Device(
                        Name=aLight.Name + " - Color",
                        Unit=new_unit_id,
                        TypeName="Selector Switch",
                        Switchtype=18,
                        Options=colorOptions,
                        DeviceID=devID + ":CWS",
                    ).Create()
                    self.updateDevice(new_unit_id, devID)

                if aLight.Color_space == "WS" and devID + ":WS" not in unitIds:
                    new_unit_id = firstFree()
                    Domoticz.Debug("Registering: {0}:WS".format(aLight.DeviceID))
                    Domoticz.Device(
                        Name=aLight.Name + " - Color",
                        Unit=new_unit_id,
                        TypeName="Selector Switch",
                        Switchtype=18,
                        Options=WhiteOptions,
                        DeviceID=devID + ":WS",
                    ).Create()
                    self.updateDevice(new_unit_id, devID)

            # Remove registered lights no longer found on the gateway

            for aUnit in list(Devices.keys()):
                devID = str(Devices[aUnit].DeviceID)

                if devID[-3:] == ":WS":
                    devID = devID[:-3]

                if devID[-4:] == ":CWS":
                    devID = devID[:-4]

                if devID[-4:] == ":RGB":
                    devID = devID[:-4]

                if not devID in ikeaIds:
                    Devices[aUnit].Delete()

            self.hasTimedOut = False
        except (HandshakeError, ReadTimeoutError, WriteTimeoutError):
            Domoticz.Debug("Connection to gateway timed out")
            self.hasTimedOut = True
        
    def onStart(self):
        Domoticz.Debug("onStart called")

        if _globalError is not None:
            Domoticz.Error("Failed to initialize tradfri module.")
            Domoticz.Error(_globalError)
            return
            
        try:
            if Parameters["Mode6"] == "Debug":
                Domoticz.Debugging(1)
                set_debug_level(1)

            self.pollInterval = int(Parameters["Mode3"])
            self.lastPollTime = datetime.datetime.now()

            set_transition_time(Parameters["Mode4"])
            self.registerDevices()
        except NameError:
            Domoticz.Error("Failed to initialize tradfri module.")
        except ApiNotFoundError as e:
            Domoticz.Error("Failed to initialize tradfri module.")
            Domoticz.Error(e.message)
        
    def onStop(self):
        Domoticz.Debug("Stopping IKEA Tradfri plugin")

        Domoticz.Debug(
            "Threads still active: " + str(threading.active_count()) + ", should be 1."
        )
        while threading.active_count() > 1:
            for thread in threading.enumerate():
                if thread.name != threading.current_thread().name:
                    Domoticz.Debug(
                        "'"
                        + thread.name
                        + "' is still running, waiting otherwise Domoticz will crash on plugin exit."
                    )
            time.sleep(1.0)

        Domoticz.Debugging(0)

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("onConnect called")

    def onMessage(self, Connection, Data):
        Domoticz.Debug("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug(
            "onCommand called for Unit "
            + str(Unit)
            + ": Parameter '"
            + str(Command)
            + "', Level: "
            + str(Level)
        )
        try:
            if Command == "On":
                self.lights[Unit].State = 1
                self.updateDevice(Unit)
                if self.lights[Unit].Type == "Blind":
                    self.devicesMoving.append(Unit)
                return

            if Command == "Off":
                self.lights[Unit].State = 0
                self.updateDevice(Unit)
                if self.lights[Unit].Type == "Blind":
                    self.devicesMoving.append(Unit)
                return

            if Command == "Set Level":
                if Devices[Unit].DeviceID[-4:] == ":CWS":
                    self.lights[Unit].Color_level = Level
                if Devices[Unit].DeviceID[-3:] == ":WS":
                    self.lights[Unit].Color_level = Level
                else:
                    if self.lights[Unit].Type == "Blind":
                        self.lights[Unit].Level = int(Level)
                        self.devicesMoving.append(Unit)
                    else:
                        self.lights[Unit].Level = int(Level * 2.54)

                if self.lights[Unit].Type == "Group":
                    self.updateDevice(Unit, override_level=Level)
                else:
                    self.updateDevice(Unit)
        except (HandshakeError, ReadTimeoutError, WriteTimeoutError):
            comObj = {"Unit": Unit, "Command": Command, "Level": Level}
            Domoticz.Debug("Command timed out. Pushing {} onto commandQueue".format(comObj))
            self.commandQueue.append(comObj)

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Debug(
            "Notification: "
            + Name
            + ","
            + Subject
            + ","
            + Text
            + ","
            + Status
            + ","
            + str(Priority)
            + ","
            + Sound
            + ","
            + ImageFile
        )

    def onDisconnect(self, Connection):
        Domoticz.Debug("onDisconnect called")

    def onHeartbeat(self):
        # Domoticz.Debug("onHeartbeat called")

        for aUnit in self.devicesMoving:
            Domoticz.Debug(
                "Device {} has moving flag set".format(self.lights[aUnit].DeviceID)
            )
            if self.updateDevice(aUnit) is False:
                self.devicesMoving.remove(aUnit)

        for aCommand in self.commandQueue:
            Domoticz.Debug("Trying to execute {} from commandQueue".format(aCommand))
            self.commandQueue.remove(aCommand)
            self.onCommand(aCommand["Unit"], aCommand["Command"], aCommand["Level"], None)

        if self.hasTimedOut:
            Domoticz.Debug("Timeout flag set, retrying...")
            self.hasTimedOut = False
            self.registerDevices()
        else:
            if Parameters["Mode2"] == "True":
                if self.lastPollTime is None:
                    Domoticz.Error("Plugin not intialized!")
                else:
                    interval = (datetime.datetime.now() - self.lastPollTime).seconds
                    if interval + 1 > self.pollInterval:
                        self.lastPollTime = datetime.datetime.now()
                        self.indexRegisteredDevices()


global _plugin
_plugin = BasePlugin()


def onStart():
    global _plugin
    _plugin.onStart()


def onStop():
    global _plugin
    _plugin.onStop()


def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)


def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)


def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)


def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)


def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)


def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions


def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return


def firstFree():
    for num in range(1, 250):
        if num not in Devices:
            return num
    return
