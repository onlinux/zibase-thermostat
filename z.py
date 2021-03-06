#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Author: Eric Vandecasteele (c)2014
# http://blog.onlinux.fr
#
#
# Import required Python libraries
#
# Installation libraries: sudo pip install pywapi
#
import os
import pygame
import time
import pywapi
import logging
import signal
import sys
import threading
import pprint
import json
from datetime import datetime
import requests
import fnmatch
from thermostat import Thermostat
from icon import Icon, Button
from snipshelpers.config_parser import SnipsConfigParser

# Give the system a quick break
time.sleep(0.5)

pp = pprint.PrettyPrinter(indent=4)

CONFIG_INI = "/config.ini"

# set up the colors
BLACK = (0,   0,   0)
WHITE = (255, 255, 255)
RED = (255,   0,   0)
GREEN = (0, 255,   0)
BLUE = (0,   0, 255)
MYGREEN = (0,  96,  65)
DARKORANGE = (255, 140, 0)
YELLOW = (255, 255,   0)
DARKGREEN = (0, 100,   0)
NAVY = (0,   0, 128)
LIGHTBLUE = (0, 113, 188)

# os.path.realpath returns the canonical path of the specified filename,
# eliminating any symbolic links encountered in the path.
path = os.path.dirname(os.path.realpath(sys.argv[0]))
configPath = path + CONFIG_INI
installPath = path + '/VClouds Weather Icons/'
logfile = path + '/thermostat.log'
logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                    filename=logfile, level=logging.DEBUG)

# Default locationCode (Toulouse-FRXX0099)
index = 0
tlocations = (
    {'code': 'FRXX0099', 'color': BLACK},
    {'code': 'FRXX4269', 'color': BLACK},
    {'code': 'FRXX3651', 'color': BLACK},
    {'code': 'BRXX3505', 'color': DARKGREEN}
)
locationCode = tlocations[index]

backgroundColor = BLUE


def renderMode(lcd, color=(0,   0,   0)):
    # Display mode
    font = fontTemp
    textAnchorY = 120
    text = font.render(thermostat.mode, True, (255, 255, 255))
    size = font.size(thermostat.mode)
    textrect = text.get_rect()
    lcd.fill(color, (70, textAnchorY, 180, size[1] + 2))
    textrect.center = (160, textAnchorY + int(size[1] / 2))
    lcd.blit(text, textrect)


def renderSetpointDay(lcd, color=(0,   0,   0)):
    font = fontTemp
    # Display setpoint Day
    textAnchorY = 10
    str = tempStr(thermostat.setpointDayValue)
    text = font.render(str, True, (255, 255, 255))
    size = font.size(str)
    textrect = text.get_rect()
    lcd.fill(color, (120, textAnchorY, 120, size[1] + 2))
    textrect.center = (175, textAnchorY + int(size[1] / 2))
    lcd.blit(text, textrect)
    lcd.blit(iconDay.bitmap, (80, textAnchorY))


def renderSetpointNight(lcd, color=(0,   0,   0)):
    font = fontTemp
    # Display setpoint Night
    textAnchorY = 65
    str = tempStr(thermostat.setpointNightValue)
    text = font.render(str, True, (255, 255, 255))
    size = font.size(str)
    textrect = text.get_rect()
    lcd.fill(color, (120, textAnchorY, 120, size[1] + 2))
    textrect.center = (175, textAnchorY + int(size[1] / 2))
    lcd.blit(text, textrect)
    lcd.blit(iconNight.bitmap, (80, textAnchorY))


def tempStr(value):

    if type(value) == int:
        temp = "{:d}".format(value)
    else:
        temp = "{:.1f}".format(value)
    temp = temp + u'\N{DEGREE SIGN}' + 'C'
    return temp


def dec2bin(n):
    if n == 0:
        return ''
    else:
        return dec2bin(n / 2) + str(n % 2)


def search(list, key, value):
    for item in list:
        if item[key] == value:
            return item


def handler(signum=None, frame=None):
    logging.debug(' Signal handler called with signal ' + str(signum))
    time.sleep(1)  # here check if process is done
    logging.debug(' Wait done')
    pygame.display.quit()
    sys.exit(0)


for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    logging.debug(' Registering handler for signal %s' % (sig))
    signal.signal(sig, handler)


class PiTft:
    'Pi Tft screen class'
    screen = None

    def __init__(self, bgc=BLACK):
        """
                Initializes a new pygame screen using the framebuffer.
                Based on "Python GUI in Linux frame buffer
                """
        disp_no = os.getenv("DISPLAY")
        if disp_no:
            print "I'm running under X display = {0}".format(disp_no)

        try:
            pygame.display.init()
        except pygame.error:
            print 'Driver:  failed.'

        pygame.display.set_caption('Zibase Pi')
        size = (320, 240)
        print("Framebuffer size: %d x %d" % (size[0], size[1])	)
        self.screen = pygame.display.set_mode(size)
        pygame.mouse.set_visible(True)
        # Clear the screen to start
        self.bgc = bgc
        self.screen.fill(self.bgc)
        # Initialise font support
        pygame.font.init()
        # Render the screen
        pygame.display.update()

    def __del__(self):
        # Destructor to make sure pygame shuts down, etc."
        print "del pygame instance"

    def clear(self, colour=None):
        if colour == None:
            colour = self.bgc
        self.screen.fill(colour)
        logging.debug(' Clear screen')

    def setBackgroundColour(self, colour=None):
        if colour != None:
            self.bgc = colour


class RenderTimeThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        #
        if (display == 1):
            textAnchorX = 0
            textAnchorY = 170
            text_surface = fontTime.render(
                time.strftime('%H:%M:%S'), True, WHITE)
            rect = text_surface.get_rect()
            lcd.fill(tlocations[index]['color'],
                     rect.move(textAnchorX, textAnchorY))
            lcd.blit(text_surface, (textAnchorX, textAnchorY))

        # refresh the screen with all the changes
        pygame.display.update()


class RenderProbeThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        try:
            config = SnipsConfigParser.read_configuration_file(configPath)
            # print configPath, config
        except:
            config = None
            print "Read config.ini error"
            return

        start = time.time()
        zibaseId = config.get('secret').get('zibaseid')
        tokenId = config.get('secret').get('tokenid')
        url = 'http://zibase2.net/api/get/ZAPI.php?zibase={}&token={}&service=get&target=home'.format(
            zibaseId, tokenId)

        try:
            resp = requests.get(url)
        except:
            print "resp exception when getting {}".format(url)
            logging.warning('RESP EXCEPTION WHEN GETTING  %s' %
                            (threading.current_thread()))
            resp = None
            return

        elapsed = (time.time() - start) * 1000
        logging.debug(' RETRIEVE DATA FROM ZIBASE.NET  [%d ms]' % (elapsed))
        data = json.loads(resp.text)
        probes = data['body']['probes']
        textAnchorY = -25
        textYoffset = 32
        scope.clear(BLACK)

        for i, v in enumerate(probes):
            #print i,v
            name = v['name'].encode('raw_unicode_escape').decode('utf-8')
            name = name.upper()
            id = v['id']
            if v['type'] == 'temperature' and id != 'TT13' and id != 'OS439156754' and name != 'FGMS001':
                #print v
                timestr = ''
                temp = ''
                hum = ''
                if 'val1' in v:
                    temp = "{:.1f}".format(v['val1'])
                    temp = temp + u'\N{DEGREE SIGN}' + 'C'
                if 'val2' in v and v['val2'] > 0:
                    hum = str(v['val2']) + '%'
                if 'time' in v:
                    timestr = str(datetime.fromtimestamp(v['time']))
                    textAnchorY += textYoffset
                    #print timestr, id, temp, hum, name, textAnchorX, textAnchorY
                    logging.debug(' %s %s %s %s %s ' %
                                  (timestr, id, temp, hum, name))
                    text = zfontSm.render(name + ' ', True, BLACK, LIGHTBLUE)
                    size = zfontSm.size(name)
                    textrect = text.get_rect()
                    textrect.topright = (170, textAnchorY + 8)
                    lcd.blit(logoLightBlue,
                             (170 - size[0] - 20, textAnchorY + 8))
                    lcd.blit(text, textrect)
                    # textAnchorY+=textYoffset
                    text = zfontTemp.render(temp, True, WHITE)
                    textrect = text.get_rect()
                    textrect.topright = (300, textAnchorY)
                    lcd.blit(text, textrect)

                pygame.display.update()


class RenderThermostatSettingThread(threading.Thread):
    #global buttons
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        thermostat.read()
        scope.clear(BLACK)

        # Draw all buttons
        for i, b in enumerate(buttons[4]):
            pp.pprint(b)
            b.draw(lcd)

        # Display setpoint Day
        renderSetpointDay(lcd)

        # Display setpoint Night
        renderSetpointNight(lcd)

        # Display mode
        renderMode(lcd)

        # Update display
        pygame.display.update()

    def __del__(self):
        class_name = self.__class__.__name__
        print class_name, "destroyed"


class RenderThermostatThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        thermostat.read()

        textAnchorY = 0
        textYoffset = 32

        scope.clear(BLACK)

        # Render time
        timeStr = time.strftime('%H:%M')
        text = fontTemp.render(timeStr, True, WHITE)
        size = fontTemp.size(timeStr)
        textrect = text.get_rect()
        textrect.topleft = (5, textAnchorY)
        lcd.blit(text, textrect)
        if thermostat.isNight:
            icon = iconNight
        else:
            icon = iconDay
        lcd.blit(icon.bitmap, (100, textAnchorY))

        timeStr = u'Ext ' + thermostat.outdoorTemp
        text = fontTemp.render(timeStr, True, WHITE)
        size = fontTemp.size(timeStr)
        textrect = text.get_rect()
        textrect.topright = (315, textAnchorY)
        lcd.blit(text, textrect)

        textAnchorY = + size[1] + 15
        # Display indoor temperature
        size = fontTempHuge.size(thermostat.indoorTemp)
        color = WHITE
        if thermostat.isOn:
            color = DARKORANGE
        text = fontTempHuge.render(thermostat.indoorTemp, True, color)
        textrect = text.get_rect()
        textrect.center = (160, textAnchorY + size[1] / 2)
        lcd.blit(text, textrect)

        textAnchorY = + int(size[1] * 1.45)

        # Display setpoint Day
        text = fontTemp.render(thermostat.setpointDay, True, WHITE)
        textrect = text.get_rect()
        textrect.topleft = (48, textAnchorY + textYoffset)
        lcd.blit(text, textrect)
        lcd.blit(iconDay.bitmap, (5, textAnchorY + textYoffset))

        # Display setpoint Night
        text = fontTemp.render(thermostat.setpointNight, True, WHITE)
        textrect = text.get_rect()
        textrect.topright = (315, textAnchorY + textYoffset)
        lcd.blit(text, textrect)
        lcd.blit(iconNight.bitmap, (180, textAnchorY + textYoffset))

        # Display mode
        text = fontTemp.render('mode ' + thermostat.mode, True, WHITE)
        textrect = text.get_rect()
        textrect.topleft = (50, textAnchorY + textYoffset * 2)
        lcd.blit(text, textrect)
        icon = iconOff
        if thermostat.isOn:
            icon = iconFlame
        lcd.blit(icon.bitmap, (7, textAnchorY + textYoffset * 2))

        pygame.display.update()

# Each request  gets its own thread


class RenderThread(threading.Thread):
    def __init__(self, location):
        threading.Thread.__init__(self)
        self.location = location
        self.code = self.location['code']
        print 'code station:', self.code

    def run(self):
        try:
            start = time.time()
            weather_com_result = pywapi.get_weather_from_weather_com(
                self.code, units='metric')
            elapsed = (time.time() - start) * 1000

            pp.pprint(weather_com_result)

            # extract current data for today
            # today = weather_com_result['current_conditions']['last_updated']

            windSpeed = weather_com_result['current_conditions']['wind']['speed']
            if windSpeed.isdigit():
                currWind = "{:.0f}km/h ".format(int(windSpeed)) + \
                    weather_com_result['current_conditions']['wind']['text']
            else:
                currWind = windSpeed
            logging.debug(' retrieve today wind')
            # currTemp = weather_com_result['current_conditions']['temperature'] + u'\N{DEGREE SIGN}' + "C"
            currTempAndHum = weather_com_result['current_conditions']['temperature'] + \
                u'\N{DEGREE SIGN}' + "C" + " / " + \
                weather_com_result['current_conditions']['humidity'] + "%"
            currPress = weather_com_result['current_conditions']['barometer']['reading'][:-3] + " hPa"
            uv = "UV {}".format(
                weather_com_result['current_conditions']['uv']['text'])
            # humid = "Hum {}%".format(weather_com_result['current_conditions']['humidity'])
            locationName = weather_com_result['location']['name']
            city = locationName.split(',')[0]
            logging.debug(' retrieve data from weather.com for %s (%s) [%d ms]' % (
                self.code, locationName, elapsed))

            # extract forecast data
            forecastDays = {}
            forecaseHighs = {}
            forecaseLows = {}
            forecastPrecips = {}
            forecastWinds = {}

            start = 0
            try:
                float(weather_com_result['forecasts']
                      [0]['day']['wind']['speed'])
            except ValueError:
                start = 1

            for i in range(start, 5):

                if not(weather_com_result['forecasts'][i]):
                    break
                forecastDays[i] = weather_com_result['forecasts'][i]['day_of_week'][0:3]
                forecaseHighs[i] = weather_com_result['forecasts'][i]['high'] + \
                    u'\N{DEGREE SIGN}' + "C"
                forecaseLows[i] = weather_com_result['forecasts'][i]['low'] + \
                    u'\N{DEGREE SIGN}' + "C"
                forecastPrecips[i] = weather_com_result['forecasts'][i]['day']['chance_precip'] + "%"
                forecastWinds[i] = "{:.0f}".format(int(weather_com_result['forecasts'][i]['day']['wind']['speed'])) + \
                    weather_com_result['forecasts'][i]['day']['wind']['text']

            # blank the screen
            lcd.fill(self.location['color'])

            # Render the weather logo at 0,0
            icon = installPath + \
                (weather_com_result['current_conditions']['icon']) + ".png"
            logo = pygame.image.load(icon).convert_alpha()
            lcd.blit(logo, (140, 0))

            # set the anchor for the current weather data text
            textAnchorX = 0
            textAnchorY = 5
            textYoffset = 20

            # add current weather data text artifacts to the screen
            text_surface = font.render(city, True, WHITE)
            lcd.blit(text_surface, (textAnchorX, textAnchorY))
            textAnchorY += textYoffset
            text_surface = font.render(currTempAndHum, True, WHITE)
            lcd.blit(text_surface, (textAnchorX, textAnchorY))
            textAnchorY += textYoffset
            text_surface = font.render(currWind, True, WHITE)
            lcd.blit(text_surface, (textAnchorX, textAnchorY))
            textAnchorY += textYoffset
            text_surface = font.render(currPress, True, WHITE)
            lcd.blit(text_surface, (textAnchorX, textAnchorY))
            textAnchorY += textYoffset
            text_surface = font.render(uv, True, WHITE)
            lcd.blit(text_surface, (textAnchorX, textAnchorY))
            textAnchorY += textYoffset
            #text_surface = font.render(humid, True, WHITE)
            #lcd.blit(text_surface, (textAnchorX, textAnchorY))

            if (display == 1):
                thermostat.read()
                textAnchorY += textYoffset
                text_surface = fontTemperature.render(
                    thermostat.indoorTemp, True, WHITE)
                lcd.blit(text_surface, (textAnchorX, textAnchorY))

            # set X axis text anchor for the forecast text
            textAnchorX = 0
            textXoffset = 65
            if (display == 0):
                # add each days forecast text
                for i in forecastDays:
                    textAnchorY = 130
                    text_surface = fontSm.render(
                        forecastDays[int(i)], True, WHITE)
                    lcd.blit(text_surface, (textAnchorX, textAnchorY))
                    textAnchorY += textYoffset
                    text_surface = fontSm.render(
                        forecaseHighs[int(i)], True, WHITE)
                    lcd.blit(text_surface, (textAnchorX, textAnchorY))
                    textAnchorY += textYoffset
                    text_surface = fontSm.render(
                        forecaseLows[int(i)], True, WHITE)
                    lcd.blit(text_surface, (textAnchorX, textAnchorY))
                    textAnchorY += textYoffset
                    text_surface = fontSm.render(
                        forecastPrecips[int(i)], True, WHITE)
                    lcd.blit(text_surface, (textAnchorX, textAnchorY))
                    textAnchorY += textYoffset
                    text_surface = fontSm.render(
                        forecastWinds[int(i)], True, WHITE)
                    lcd.blit(text_surface, (textAnchorX, textAnchorY))
                    textAnchorX += textXoffset

            # refresh the screen with all the changes
            pygame.display.update()
            #logging.debug(" End of thread: %s -> %s for %s" % (threading.current_thread(), today, locationName))

        except ValueError:
            logging.warning(' PYWAPI %s CONNECTION ERROR ' %
                            (threading.current_thread()))
            scope.clear()
            title = 'ERROR'
            text = fontTitle.render(title, True, WHITE)
            textrect = text.get_rect()
            textrect.center = (160, 20)
            lcd.blit(text, textrect)
            pygame.display.update()


def showNextLocation(channel):
    global index
    global lastupdate
    if (time.time() - lastupdate > 2):
        if (index < len(tlocations) - 1):
            index += 1
        else:
            index = 0
        location = tlocations[index]
        RenderThread(location).start()
        lastupdate = time.time()
    time.sleep(0.5)


def showNextDisplay(channel):
    global display
    global lastupdate
    global updateRate

    if (display < 3):
        display += 1
    else:
        display = 0

    if display == 2 or display == 3:
        updateRate = 60
    else:
        updateRate = 60 * 5

    logging.debug(' Display[%d], set delay to %d s' % (display, updateRate))
    print('showNextDisplay %d' % (display))
    #location = tlocations[index]
    # RenderThread(location).start()
    lastupdate = 0
    time.sleep(0.5)


def settingCallback(n):
    global thermostat
    global display

    print("Calling " + str(n))
    if n == 6:
        thermostat.nextMode()
        renderMode(lcd)
    elif n == 5:
        thermostat.prevMode()
        renderMode(lcd)
    elif n == 2:
        thermostat.addSetpointDay(0.1)
        renderSetpointDay(lcd)
    elif n == 1:
        thermostat.addSetpointDay(-0.1)
        renderSetpointDay(lcd)
    elif n == 4:
        thermostat.addSetpointNight(0.1)
        renderSetpointNight(lcd)
    elif n == 3:
        thermostat.addSetpointNight(-0.1)
        renderSetpointNight(lcd)
    elif n == 7:
        print "cancel"
        display = 3
        RenderThermostatThread().start()
    elif n == 8:
        print 'update values'
        display = 3
        thermostat.update()
        RenderThermostatThread().start()

    # Update display
    pygame.display.update()


def callback(n):
    global display
    print 'Display', display, 'arg:', n
    if n == 3:
        display = 4
        RenderThermostatSettingThread().start()


# Create an instance of the PiTft class
scope = PiTft()
scope.clear()

lcd = scope.screen

icons = []  # This list gets populated at startup

buttons = [
    # Screen 0 Meteo & forecasts
    [Button((30,  0, 320, 240), bg='box', cb=showNextLocation, value=0)],
    # Screen 1 Meteo , temperature & clock
    [Button((30,  0, 320, 240), bg='box', cb=showNextLocation, value=1)],
    # Screen 2 Temperature Probes
    [Button((30,  0, 320, 240), bg='box', cb=callback, value=2)],
    # Screen 3 Thermostat
    [Button((30,  0, 320, 240), bg='box', cb=callback, value=3)],
    # Screen 4 Thermostat settings
    [Button((5, 5, 50, 50), bg='left-50',   cb=settingCallback,    value=1),
        Button((265, 5, 50, 50), bg='right-50', cb=settingCallback,  value=2),
        Button((5, 60, 50, 50), bg='left-50',  cb=settingCallback,  value=3),
        Button((265, 60, 50, 50), bg='right-50',
               cb=settingCallback,     value=4),
        Button((5, 115, 50, 50), bg='left-50',
               cb=settingCallback,     value=5),
        Button((265, 115, 50, 50), bg='right-50',
               cb=settingCallback,    value=6),
        Button((5, 185, 116, 50), bg='cancel-50',
               cb=settingCallback,  value=7),
        Button((199, 185, 116, 50), bg='ok-50',
               cb=settingCallback,    value=8),
     ]
]

iconPath = path + '/icons'  # Subdirectory containing UI bitmaps (PNG format)

print "Loading Icons..."
# Load all icons at startup.
for file in os.listdir(iconPath):
    if fnmatch.fnmatch(file, '*.png'):
        #print file
        icons.append(Icon(iconPath, file.split('.')[0]))
# Assign Icons to Buttons, now that they're loaded
print"Assigning Buttons"
for s in buttons:        # For each screenful of buttons...
    for b in s:  # For each button on screen...
        for i in icons:  # For each icon...
            if b.bg == i.name:  # Compare names; match?
                b.iconBg = i  # Assign Icon to Button
                b.bg = None  # Name no longer used; allow garbage collection
            if b.fg == i.name:
                b.iconFg = i
                b.fg = None

# set up the fonts
fontpath = pygame.font.match_font('dejavusansmono')
zfontpath = path + '/fonts/HandelGotD.ttf'
logging.debug(' zfontpath %s' % (zfontpath))
logging.debug(' fontpath %s' % (fontpath))
# set up 2 sizes
font = pygame.font.Font(fontpath, 18)
fontSm = pygame.font.Font(fontpath, 18)
fontTemperature = pygame.font.Font(fontpath, 40)
fontTime = pygame.font.Font(fontpath, 64)

fontTitle = pygame.font.Font(zfontpath, 48)
fontTempHuge = pygame.font.Font(zfontpath, 90)
fontTemp = pygame.font.Font(zfontpath, 32)

zfont = pygame.font.Font(zfontpath, 18)
zfontSm = pygame.font.Font(zfontpath, 15)
zfontTemp = pygame.font.Font(zfontpath, 30)

# load background label icon
iconOrange = path + '/icons/DateOrange.png'
logoOrange = pygame.image.load(iconOrange).convert_alpha()
iconBlue = path + '/icons/DateLightBlue.png'
logoLightBlue = pygame.image.load(iconBlue).convert_alpha()

# load thermostat icon set
fontTemp = pygame.font.Font(zfontpath, 32)
iconDay = Icon(path, '/icons/sun-2-32')
iconNight = Icon(path, '/icons/moon-2-32')
iconOff = Icon(path, '/icons/off')
iconFlame = Icon(path, '/icons/flame32')

zibaseId = None
tokenId = None
try:
    config = SnipsConfigParser.read_configuration_file(configPath)
    #print configPath, config
    zibaseId = config.get('secret').get('zibaseid')
    tokenId = config.get('secret').get('tokenid')
except:
    config = None

thermostat = Thermostat(config)

display = 3  # Set the Default display here

# update interval in seconds
if display == 2 or display == 3:
    updateRate = 60
else:
    updateRate = 60 * 5

lastupdate = 0

# define a variable to control the main loop
running = True
try:

    time_stamp = time.time()

    while running:
        now = time.time()

        if now > lastupdate + updateRate:
            if display == 2:
                RenderProbeThread().start()
            elif display == 3:
                RenderThermostatThread().start()
            elif display == 0 or display == 1:
                RenderThread(tlocations[index]).start()

            logging.debug(' DISPLAY %s' % (display))
            lastupdate = int(now / 60) * 60
            timestr = str(datetime.fromtimestamp(now + updateRate))
            logging.debug(' Next update @ %s' % (timestr))

        if (display == 1):
            RenderTimeThread().start()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                    # change the value to False, to exit the main loop
                running = False

            pressed_keys = pygame.key.get_pressed()

            if pressed_keys[pygame.K_PAGEDOWN] or pressed_keys[pygame.K_n]:
                showNextDisplay(1)

            if pressed_keys[pygame.K_ESCAPE]:
                print 'K_ESCAPE'
                running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                print "screen pressed"  # for debugging purposes
                pos = (pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1])
                print pos  # for checking
                # for debugging purposes - adds a small dot where the screen is pressed
                pygame.draw.circle(lcd, WHITE, pos, 2, 0)
                # if display < 2:
                # showNextLocation(1)
                for b in buttons[display]:
                    if b.selected(pos):
                        break

        time.sleep(0.2)
finally:
    logging.info("  Quit")
