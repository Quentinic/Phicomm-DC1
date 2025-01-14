# Phicomm DC1 Python Plugin
#
# Author: Eric
#
"""
<plugin key="Phicomm-DC1" name="Phicomm DC1 Plug" author="Eric" version="1.0.0" externallink="https://github.com/EricInBj/Phicomm-DC1">
	<params>
        <param field="Mode1" label="更新频率(秒)" width="30px" required="true" default="30"/>
    </params>
</plugin>
"""
import Domoticz
import socket
import json
import re
import time
import binascii

class plugin:
	serverConn = None
	clientConns = {}	
	intervalTime = 0
	heartBeatFreq = 10
	devicesMap = {'45':'fish','46':'cat'}
	

	def generateIdentityTag(self, addr):
		Domoticz.Log('Generating device tag for : '+addr)
		ips = addr.split('.')
		identity = ips[1] + ips[2] + ips[3] # use ip address without 1st prefix as unique identify to avoid conflict

		return identity


	def idx_to_key(self, arg):
		keys = {
		0: {'name':u"总开关", 'type':'Switch'},
		1: {'name':u"一位", 'type':'Switch'},
		2: {'name':u"二位", 'type':'Switch'},
		3: {'name':u"三位", 'type':'Switch'},
		4: {'name':u'电压', 'type':'Voltage'},
		5: {'name':u'功率', 'type':'kWh'}
		}    
		return keys.get(arg, {'name':u"总开关", 'type':'Switch'})
	

	def deviceid_to_name(self, deviceTag):
		if deviceTag in self.devicesMap.keys():
			return self.devicesMap[deviceTag]
		else:
			return deviceTag
		


	def createDevices(self, deviceTag):
		#Create 6 devices (include 4 switches and 1 voltage device, 1 Kwh device)
		Domoticz.Debug("Devices count: " + str(len(Devices)))
		for i in range(0,6):
			deviceID = deviceTag + str(i)
			unitid = len(Devices) + 1

			if self.getExistingDevice(deviceID) == None:
				options = {}
				if self.idx_to_key(i)['type'] == 'kWh':
					#options['EnergyMeterMode'] = '1'

					Domoticz.Device(
						DeviceID=deviceID, Name= '%s_%s' %(self.deviceid_to_name(deviceTag), self.idx_to_key(i)['name']),  
						Unit=unitid, TypeName=self.idx_to_key(i)['type'], Options=options, Used=1
					).Create()
				else:
					Domoticz.Device(
						DeviceID=deviceID, Name= '%s_%s' %(self.deviceid_to_name(deviceTag), self.idx_to_key(i)['name']),  
						Unit=unitid, TypeName=self.idx_to_key(i)['type'], Used=1
					).Create()


	def updateDevices(self, deviceTag, data):
		switchStatus = str(data['status']).zfill(4)[::-1]
		for i in range(0,4):
			deviceID = deviceTag + str(i)

			value = 'On' if switchStatus[i:i+1] == '1' else 'Off'
			self.updateDevice(deviceID, int(switchStatus[i:i+1]), value)

		self.updateDevice(deviceTag + str(4), int(data['V']), data['V'])
		#self.updateDevice(deviceTag + str(5), int(data['P']), data['P'])
		self.updateDevice(deviceTag + str(5), 0, str(data['P']) + ';' + str(data['P']))

		return None
		

	def updateDevice(self, deviceid, nValue, sValue):
		device = self.getExistingDevice(deviceid)
		if device is not None:
			if (device.nValue != nValue) or (device.sValue != sValue):
				device.Update(nValue=nValue, sValue=str(sValue))
				Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' for ("+device.Name+")")
		return None


	def getExistingDevice(self, identity):
		for x in Devices:
			if str(Devices[x].DeviceID) == identity:
				return Devices[x]
		return None


	def checkState(self, deviceTag):
		if deviceTag in self.clientConns:
			conn = self.clientConns[deviceTag]
			if conn != None:
				conn.Send(bytes('{"uuid":"T%s","params":{ },"auth":"","action":"datapoint"}\n' % str(round(time.time() * 1000)),encoding="utf8"))


	def onStart(self):

		self.repeatTime = int(Parameters["Mode1"])
		#self.devicesMap = json.loads(Parameters["Model2"])

		Domoticz.Heartbeat(self.heartBeatFreq)
		self.serverConn = Domoticz.Connection(Name="Data Connection", Transport="TCP/IP", Protocol="line", Port="8000")
		self.serverConn.Listen()

		#self.createDevices('45')

		Domoticz.Log("successfully listen at: "+self.serverConn.Address+":"+self.serverConn.Port)


	def onStop(self):
		Domoticz.Log("onStop called")
		if self.serverConn.Connected():
			self.serverConn.Disconnect()


	def onConnect(self, Connection, Status, Description):
		if (Status == 0):
			Domoticz.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port)
		else:
			Domoticz.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description)
		
		Connection.Send(bytes('{"uuid":"T%s","params":{ },"auth":"","action":"datapoint"}\n' % str(round(time.time() * 1000)),encoding="utf8"))

		Domoticz.Log(str(Connection))
		identityTag = self.generateIdentityTag(Connection.Address)
		Domoticz.Log("Generated device tag: " + identityTag)
		
		self.clientConns[identityTag] = Connection


	def onMessage(self, Connection, Data):
		try:
			#{"action":"activate=","uuid":"activate=1da","auth":"","params":{"device_type":"PLUG_DC1_7","mac":"A4:7B:9D:00:14:C5"}}
			#{"uuid":"T1558098110443","status":200,"result":{"status":1011,"I":129,"V":223,"P":22},"msg":"get datapoint success"}
			Domoticz.Log("onMessage called for connection: "+Connection.Address+":"+Connection.Port)	
			Domoticz.Log("Data: "+bytes.decode(Data))	
			data = json.loads(bytes.decode(Data))
			deviceTag = self.generateIdentityTag(Connection.Address)
			
			if 'action' in data.keys():
				#new connection from dc1, create devices
				self.createDevices(deviceTag)

			elif 'status' in data.keys() and data['status'] == 200:
				#data from dc1, update devices
				self.updateDevices(deviceTag, data['result']) #result":{"status":1011,"I":129,"V":223,"P":22}
		except Exception as ex:
			Domoticz.Log(str(ex))


	def onCommand(self, Unit, Command, Level, Hue):
		Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
		deviceID = Devices[Unit].DeviceID

		# identifier for a single phicomm smart plug
		deviceTag = deviceID[0:len(deviceID) - 1]
		# get the device identity id which stands for device type. 0 - Main Switch, 1 - No.1 switch, 2 - No.2 switch, 3 - No.3 switch
		identityID = deviceID[-1]

		Domoticz.Log('Unit: %s, DeviceTag: %s, DeviceID: %s, IdentityID: %s'%(Unit, deviceTag, deviceID, identityID))

		if deviceTag in self.clientConns:
			conn = self.clientConns[deviceTag]
			if conn != None:
				uuid = int(round(time.time() * 1000))

				i = 0
				# No.3 switch
				if self.getExistingDevice(deviceTag + str(3)).nValue == 1:
					i |= 0b1000
				# No.2 switch
				if self.getExistingDevice(deviceTag + str(2)).nValue == 1:
					i |= 0b100
				# No.1 switch
				if self.getExistingDevice(deviceTag + str(1)).nValue == 1:
					i |= 0b10
				# Main Switch
				if self.getExistingDevice(deviceTag + str(0)).nValue == 1:
					i |= 0b1
					
				if Command == 'Off':
					i &= ~(1 << int(identityID))
				else:
					i |= 1 << int(identityID)

				strT = bin(int(i))
				Domoticz.Log('strT: %s, i: %d'%(strT, i))
				strT = strT[2:len(strT)]

				payload = bytes(
					'{"action":"datapoint=","params":{"status":' + str(strT) + '},"uuid":"' + str(uuid) + '","auth":""}\n',
					encoding="utf8")

				Domoticz.Log(str(payload))
								
				conn.Send(payload)
		else:
			Domoticz.Error('Device is not connected')
		self.checkState(deviceTag)
		
	

	def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
		Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

	def onDisconnect(self, Connection):
		if len(Connection.Address) > 0 :
			Domoticz.Log("onDisconnect called %s"%Connection.Address)
			identityTag = self.generateIdentityTag(Connection.Address)
			if identityTag in self.clientConns:
				self.clientConns.pop(identityTag)
				print("drop connect "+Connection.Address)


	def onHeartbeat(self):
		if self.repeatTime == 0:
			return
		self.intervalTime += self.heartBeatFreq
		#Domoticz.Log('onHeartbeat intervalTime=%s'%self.intervalTime)
		if self.intervalTime >= self.repeatTime:
			self.intervalTime = 0
			Domoticz.Log("send onHeartbeat....")
			for identityTag in self.clientConns:
				Domoticz.Log("send onHeartbeat to :%s"%identityTag)
				self.clientConns[identityTag].Send(bytes('{"uuid":"T%s","params":{ },"auth":"","action":"datapoint"}\n' % str(round(time.time() * 1000)),encoding="utf8"))

global _plugin
_plugin = plugin()

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
