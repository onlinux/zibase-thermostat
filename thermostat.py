#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Author: Eric Vandecasteele (c)2014
# http://blog.onlinux.fr
#
# Import required Python libraries
import time
import threading
import json
import requests
import logging


class Thermostat:
    'Common base class for thermostat'

    mode = {
        0: 'automatique',
        5: 'stop',
        6: 'hors gel',
        16: 'jour',
        32: 'tempo jour',
        48: 'nuit',
        64: 'tempo nuit'
    }

    runMode = {
        0: 'nuit',
        2: 'nuit',
        1: 'jour',
        3: 'jour'
    }

    status = {
        0: u'arrêt',
        1: u'marche'
    }

    def __init__(self, config):
        self.zibaseId = config.get('secret').get('zibaseid', None)
        self.tokenId = config.get('secret').get('tokenid', None)
        self.urlBase = "http://zibase.net/api/get/ZAPI.php?zibase={}&token={}".format(
            self.zibaseId, self.tokenId)
        self.modeList = [0, 5, 6, 16, 32, 48, 64]
        self.state = None
        self.indoorTemp = None
        self.outdoorTemp = None
        self.runningMode = None
        self.setpointDayValue = None
        self.setpointDayVariable = int(config.get(
            'global').get('setpointdayvariable', 29))
        self.setpointNightVariable = int(config.get(
            'global').get('setpointnightvariable', 30))
        self.setpointDay = None
        self.setpointNightValue = None
        self.setpointNight = None
        self.modeValue = None
        self.modeVariable = int(config.get('global').get('modevariable', 31))
        self.modeIndex = None
        self.tempVariable = int(config.get('global').get('tempvariable', 28))
        self.state = None
        self.stateVariable = int(config.get('global').get('statevariable', 13))
        self.thermostatScenario = int(config.get(
            'global').get('thermostatscenario', 32))
        self.title = 'Thermostat'

        logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                            filename='./thermostat.log', level=logging.DEBUG)

    def __del__(self):
        class_name = self.__class__.__name__
        print class_name, "destroyed"

    def rotate(self, l, y=1):
        if len(l) == 0:
            return l
        y = y % len(l)

        return l[y:] + l[:y]

    def tempStr(self, value):
        if type(value) == int:
            temp = "{:d}".format(value)
        else:
            temp = "{:.1f}".format(value)

        return temp + u'\N{DEGREE SIGN}' + 'C'

    def search(self, list, key, value):
        for item in list:
            if item[key] == value:
                return item

    def read(self):
        start = time.time()
        url = self.urlBase + '&service=get&target=home'
        resp = requests.get(url)
        elapsed = (time.time() - start) * 1000
        logging.debug(' retrieve data from zibase.net  [%d ms]' % (elapsed))

        data = json.loads(resp.text)
        probes = data['body']['probes']

        thermostat = self.search(probes, 'id', 'TT13')
        if thermostat:
            self.runningMode = int(thermostat['val2']) & 0x1

        outdoorProbe = self.search(probes, 'id', 'OS3391881217')
        if outdoorProbe:
            self.outdoorTemp = self.tempStr(int(outdoorProbe['val1']))

        variables = data['body']['variables']
        self.setpointDayValue = float(variables[self.setpointDayVariable]) / 10
        self.setpointDay = self.tempStr(self.setpointDayValue)
        self.setpointNightValue = float(
            variables[self.setpointNightVariable]) / 10
        self.setpointNight = self.tempStr(self.setpointNightValue)

        self.indoorTemp = self.tempStr(
            float(variables[self.tempVariable]) / 10)
        self.modeValue = variables[self.modeVariable]

        # Check if key variables[self.modeVariable] exists first
        try:
            self.mode = Thermostat.mode[variables[self.modeVariable]]
        except KeyError:
            logging.warning(' Key %d not present in Thermostat.mode dict' % (
                variables[self.modeVariable]))
            pass

        #   0: u'arrêt',
        #   1: u'marche'
        if variables[self.stateVariable] >= 0:
            self.state = variables[self.stateVariable] & 0x01
        else:
            self.state = 0

        # Rotate thermostatModeList to get current mode as index 3
        while self.modeList[3] != self.modeValue:
            self.modeList = self.rotate(self.modeList)
            print self.modeList

        self.modeIndex = self.modeList[3]

    def refresh(self):
        start = time.time()
        url = self.urlBase + \
            '&service=execute&target=scenario&id={}'.format(
                self.thermostatScenario)
        print url
        requests.get(url)
        elapsed = (time.time() - start) * 1000
        logging.debug(' Launch scenario thermostat_2 [%d] now!  [%d ms]' % (
            self.thermostatScenario, elapsed))

    def setVariable(self, variable, value):
        '''
        Send low level command to zibase
        param1=5 READ/WRITE_VARIABLE/CALENDAR/X10
        param3=1 WRITE variable
        param4=  # variable
        param2 = new value
        '''
        if variable < 52:
            start = time.time()
            try:
                url = 'http://zibase.net/m/zapi_remote_zibase_set.php?device={}&token={}&action=rowzibasecommand&param1=5&param3=1&param4='.format(
                    self.zibaseId, self.tokenId) + str(variable) + '&param2=' + str(value)
                print url
                requests.get(url)
                # Give the system a quick break
                time.sleep(0.5)
            except:
                print "resp exception when getting {}".format(url)
                logging.warning('RESP EXCEPTION WHEN GETTING  %s' % (url))

            elapsed = (time.time() - start) * 1000
            time.sleep(10)
            logging.debug(' setVariable  %i  to  %i zibase.net [%d ms]' % (
                int(variable), int(value), elapsed))
        else:
            logging.warning(' setVariable  [%s]  is not int' % (str(variable)))

    def setMode(self, mode):
        self.setVariable(self.modeVariable, int(mode))
        logging.debug(' Send mode %i  to zibase.net ' % (int(mode)))

    def setSetpointDay(self):
        value = int(self.setpointDayValue * 10)
        self.setVariable(self.setpointDayVariable, value)
        logging.debug(' Send setpoindDay %i  to zibase.net ' % (value))

    def setSetpointNight(self):
        value = int(self.setpointNightValue * 10)
        self.setVariable(self.setpointNightVariable, value)
        logging.debug(' Send setpoindNight %i  to zibase.net ' % (value))

    def nextMode(self):
        self.modeList = self.rotate(self.modeList)
        self.modeIndex = self.modeList[3]
        self.mode = Thermostat.mode[self.modeIndex]
        return str(self.mode)

    def prevMode(self):
        self.modeList = self.rotate(self.modeList, -1)
        self.modeIndex = self.modeList[3]
        self.mode = Thermostat.mode[self.modeIndex]
        return str(self.mode)

    def addSetpointDay(self, incr=float(0.1)):
        self.setpointDayValue += incr
        print self.setpointDayValue
        return self.tempStr(self.setpointDayValue)

    def addSetpointNight(self, incr=float(0.1)):
        self.setpointNightValue += incr
        print self.setpointNightValue
        return self.tempStr(self.setpointNightValue)

    def update(self):
        threading.Thread(target=self.setMode, args=(self.modeIndex,)).start()
        # Give the system a quick break
        time.sleep(0.5)
        threading.Thread(target=self.setSetpointDay).start()
        # Give the system a quick break
        time.sleep(0.5)
        threading.Thread(target=self.setSetpointNight).start()
        # TODO Display spinner while updating values
        time.sleep(5)
        self.refresh()
        time.sleep(1)
        #print 'threading.activeCount()', threading.activeCount(), threading.enumerate()
