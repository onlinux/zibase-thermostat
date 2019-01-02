#!/usr/bin/python
#
# Author: Eric Vandecasteele (c)2014
# http://blog.onlinux.fr
#

# Import required Python libraries
import os
import pygame
import time
import pywapi
import logging
import signal
import sys
import threading
import pprint
import RPi.GPIO as GPIO
from Zapi import ZiBase

#setup GPIO using Broadcom SOC channel numbering
GPIO.setmode(GPIO.BCM)

#Setup GPIO
#GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(27, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)

#Set up backlight GPIO
os.system("sudo sh -c 'echo 252 > /sys/class/gpio/export'")

#Give the system a quick break
time.sleep(0.5)

pp = pprint.PrettyPrinter(indent=4)

# set up the colors
BLACK = (  0,   0,   0)
WHITE = (255, 255, 255)
RED   = (255,   0,   0)
GREEN = (  0, 255,   0)
BLUE  = (  0,   0, 255)
MYGREEN = ( 0, 96, 65)
DARKORANGE = ( 255, 140 ,0)
YELLOW = ( 255, 255, 0)
DARKGREEN = (0, 100, 0)
NAVY = (0, 0, 128)

logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', filename='/var/log/piweather.log',level=logging.DEBUG)

def handler(signum = None, frame = None):
    logging.debug (' Signal handler called with signal '+ str(signum) )
    time.sleep(1)  #here check if process is done
    logging.debug( ' Wait done')
    pygame.display.quit()
    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    logging.debug (' Registering handler for signal %s' % (sig) )
    signal.signal(sig, handler)

installPath = "/home/pi/weather/VClouds Weather Icons/"

tlocations = (
				{'code': 'FRXX0099' , 'color': NAVY},
				{'code': 'FRXX4269' , 'color': NAVY},
				{'code': 'FRXX3651' , 'color': BLACK},
				{'code': 'BRXX3505' , 'color': DARKGREEN}
)

#Default locationCode (Toulouse-FRXX0099)
locationCode = tlocations[0]
backgroundColor = BLUE

class PiTft :
    screen = None;

    def __init__(self):
        "Initializes a new pygame screen using the framebuffer"
        # Based on "Python GUI in Linux frame buffer"
        disp_no = os.getenv("DISPLAY")
        if disp_no:
            print "I'm running under X display = {0}".format(disp_no)
        os.putenv('SDL_FBDEV', '/dev/fb1')
        os.putenv('SDL_MOUSEDRV', 'TSLIB')
        os.putenv('SDL_MOUSEDEV', '/dev/input/touchscreen')
        # Check which frame buffer drivers are available
        # Start with fbcon since directfb hangs with composite output
        drivers = ['fbcon', 'directfb', 'svgalib']
        found = False
        for driver in drivers:
            # Make sure that SDL_VIDEODRIVER is set
            if not os.getenv('SDL_VIDEODRIVER'):
                os.putenv('SDL_VIDEODRIVER', driver)
            try:
                pygame.display.init()
            except pygame.error:
                print 'Driver: {0} failed.'.format(driver)
                continue
            found = True
            break

        if not found:
            raise Exception('No suitable video driver found!')

        size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
        print("Framebuffer size: %d x %d" % (size[0], size[1]) )
        self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        # Clear the screen to start
        self.screen.fill((0, 0, 0))
        # Initialise font support
        pygame.font.init()
        # Render the screen
        pygame.display.update()

    def __del__(self):
        "Destructor to make sure pygame shuts down, etc."

    def test(self):
		self.screen.fill(BLUE)
		pygame.display.update()

class RenderTimeThread(threading.Thread):
    def __init__(self):
		threading.Thread.__init__(self)

    def run(self):
		# set X axis text anchor for the forecast text
		if (display == 1):
			textAnchorX = 0
			textAnchorY = 170
			text_surface = fontTime.render(time.strftime('%H:%M:%S'), True, colourWhite)
			rect = text_surface.get_rect();
			lcd.fill(tlocations[index]['color'], rect.move(textAnchorX, textAnchorY))
			lcd.blit(text_surface, (textAnchorX, textAnchorY))

		# refresh the screen with all the changes
		pygame.display.update()


# Each request  gets its own thread
class RenderThread(threading.Thread):
    def __init__(self, location):
		threading.Thread.__init__(self)
		self.location = location
		self.code = self.location['code']
    def run(self):
		try:
			start = time.time()
			weather_com_result = pywapi.get_weather_from_weather_com(self.code)
			elapsed = (time.time() - start) *1000

			#pp.pprint(weather_com_result)

			# extract current data for today
			# today = weather_com_result['current_conditions']['last_updated']
			windSpeed = int(weather_com_result['current_conditions']['wind']['speed'])
			currWind = "{:.0f}km/h ".format(windSpeed) + weather_com_result['current_conditions']['wind']['text']
			# currTemp = weather_com_result['current_conditions']['temperature'] + u'\N{DEGREE SIGN}' + "C"
			currTempAndHum = weather_com_result['current_conditions']['temperature'] + u'\N{DEGREE SIGN}' + "C" + " / "+ weather_com_result['current_conditions']['humidity'] + "%"
			currPress = weather_com_result['current_conditions']['barometer']['reading'][:-3] + " hPa"
			uv = "UV {}".format(weather_com_result['current_conditions']['uv']['text'])
			# humid = "Hum {}%".format(weather_com_result['current_conditions']['humidity'])
			locationName = weather_com_result['location']['name']
			city = locationName.split(',')[0]
			logging.debug(' retrieve data from weather.com for %s (%s) [%d ms]' % ( self.code,locationName, elapsed ) )

			# extract forecast data
			forecastDays = {}
			forecaseHighs = {}
			forecaseLows = {}
			forecastPrecips = {}
			forecastWinds = {}

			start = 0
			try:
				float(weather_com_result['forecasts'][0]['day']['wind']['speed'])
			except ValueError:
				start = 1

			for i in range(start, 5):

				if not(weather_com_result['forecasts'][i]):
					break
				forecastDays[i] = weather_com_result['forecasts'][i]['day_of_week'][0:3]
				forecaseHighs[i] = weather_com_result['forecasts'][i]['high'] + u'\N{DEGREE SIGN}' + "C"
				forecaseLows[i] = weather_com_result['forecasts'][i]['low'] + u'\N{DEGREE SIGN}' + "C"
				forecastPrecips[i] = weather_com_result['forecasts'][i]['day']['chance_precip'] + "%"
				forecastWinds[i] = "{:.0f}".format(int(weather_com_result['forecasts'][i]['day']['wind']['speed']) ) + \
					weather_com_result['forecasts'][i]['day']['wind']['text']

			# blank the screen
			lcd.fill(self.location['color'])

			# Render the weather logo at 0,0
			icon = installPath+ (weather_com_result['current_conditions']['icon']) + ".png"
			logo = pygame.image.load(icon).convert_alpha()
			lcd.blit(logo, (140, 0))

			# set the anchor for the current weather data text
			textAnchorX = 0
			textAnchorY = 5
			textYoffset = 20

			# add current weather data text artifacts to the screen
			text_surface = font.render(city, True, colourWhite)
			lcd.blit(text_surface, (textAnchorX, textAnchorY))
			textAnchorY+=textYoffset
			text_surface = font.render(currTempAndHum, True, colourWhite)
			lcd.blit(text_surface, (textAnchorX, textAnchorY))
			textAnchorY+=textYoffset
			text_surface = font.render(currWind, True, colourWhite)
			lcd.blit(text_surface, (textAnchorX, textAnchorY))
			textAnchorY+=textYoffset
			text_surface = font.render(currPress, True, colourWhite)
			lcd.blit(text_surface, (textAnchorX, textAnchorY))
			textAnchorY+=textYoffset
			text_surface = font.render(uv, True, colourWhite)
			lcd.blit(text_surface, (textAnchorX, textAnchorY))
			textAnchorY+=textYoffset
			#text_surface = font.render(humid, True, colourWhite)
			#lcd.blit(text_surface, (textAnchorX, textAnchorY))

			if (display == 1):
				try:
					info = zibase.getSensorInfo("OS439204100")
				except IOError:
					logging.warning(' %s RETRY AFTER 1 CONNECTION ERROR %s' % (threading.current_thread(), IOError) )
					time.sleep(0.5)
					try:
						info = zibase.getSensorInfo("OS439204100")
						logging.debug(' %s RETRY SUCCESSFUL  %s' % (threading.current_thread(), IOError) )
					except IOError:
						logging.warning(' %s RETRY FAILED %s' % (threading.current_thread(), IOError) )

				if (info[1]):
					textAnchorY+=textYoffset
					hum = "{:.0f}%".format(float(info[2]) )
					temp = "{:.1f}".format(float(info[1])/10) + u'\N{DEGREE SIGN}' + "C " + hum
					text_surface = fontTemp.render( temp, True, colourWhite)
					lcd.blit(text_surface, (textAnchorX, textAnchorY))

			# set X axis text anchor for the forecast text
			textAnchorX = 0
			textXoffset = 65
			if (display == 0):
				# add each days forecast text
				for i in forecastDays:
					textAnchorY = 130
					text_surface = fontSm.render(forecastDays[int(i)], True, colourWhite)
					lcd.blit(text_surface, (textAnchorX, textAnchorY))
					textAnchorY+=textYoffset
					text_surface = fontSm.render(forecaseHighs[int(i)], True, colourWhite)
					lcd.blit(text_surface, (textAnchorX, textAnchorY))
					textAnchorY+=textYoffset
					text_surface = fontSm.render(forecaseLows[int(i)], True, colourWhite)
					lcd.blit(text_surface, (textAnchorX, textAnchorY))
					textAnchorY+=textYoffset
					text_surface = fontSm.render(forecastPrecips[int(i)], True, colourWhite)
					lcd.blit(text_surface, (textAnchorX, textAnchorY))
					textAnchorY+=textYoffset
					text_surface = fontSm.render(forecastWinds[int(i)], True, colourWhite)
					lcd.blit(text_surface, (textAnchorX, textAnchorY))
					textAnchorX+=textXoffset

			# refresh the screen with all the changes
			pygame.display.update()
			#logging.debug(" End of thread: %s -> %s for %s" % (threading.current_thread(), today, locationName))

		except ValueError:
			logging.warning(' %s CONNECTION ERROR ' % (threading.current_thread()) )


#Set the intitial counter value to zero
counter = 0
def manageBacklight(channel):
	global counter
	global index
	global lastupdate
	global updateRate

	if (counter == 0):
		os.system(" sudo sh -c 'echo 'out' > /sys/class/gpio/gpio252/direction'")
		counter = 1
		logging.debug(" sudo sh -c 'echo 'out' > /sys/class/gpio/gpio252/direction'")
		updateRate = 3600 # set delay to 3600 seconds
		logging.debug(" counter now 3, set delay to 3600s")
		time.sleep(0.5)

	elif (counter == 1) or (counter == 3):
		os.system(" sudo sh -c 'echo '1' > /sys/class/gpio/gpio252/value'")
		counter = 2
		# Force refresh
		RenderThread(tlocations[index]).start()
		lastupdate = time.time()
		logging.debug(" counter now 2, set delay to 600s")
		updateRate = 600
		time.sleep(0.5)

	elif (counter == 2):
		os.system("sudo sh -c 'echo '0' > /sys/class/gpio/gpio252/value'")
		counter = 3
		updateRate = 3600 # set delay to 3600 seconds
		logging.debug(" counter now 3, set delay to 3600s")
		time.sleep(0.5)

index = 0
def showNextLocation(channel):
	global index
	global lastupdate
	if (time.time() - lastupdate > 2):
		if (index < len(tlocations) -1):
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
	if (display < 1):
		display += 1
	else:
		display = 0
	logging.debug('showNextDisplay %d' % (display))
	location = tlocations[index]
	RenderThread(location).start()
	lastupdate = time.time()
	time.sleep(0.5)

# font colours
colourWhite = (255, 255, 255)
colourBlack = (0, 0, 0)
colourBlue = (0, 0, 255)

# Create an instance of the PiTft class
scope = PiTft()
scope.test()
lcd = scope.screen

# set up the fonts
fontpath = pygame.font.match_font('dejavusansmono')
logging.debug(' fontpath %s' % (fontpath))
# set up 2 sizes
font = pygame.font.Font(fontpath, 18)
fontSm = pygame.font.Font(fontpath, 18)
fontTemp = pygame.font.Font(fontpath, 40)
fontTime = pygame.font.Font(fontpath, 64)


zibase = ZiBase.ZiBase('192.168.0.100') # Ip address of ZiBase

display = 1 # Set display 1 as default (display clock)

# update interval in seconds
updateRate = 600
lastupdate = 0

try:
	GPIO.add_event_detect(22, GPIO.FALLING, callback=manageBacklight, bouncetime=300)
	GPIO.add_event_detect(27, GPIO.FALLING, callback=showNextLocation, bouncetime=300)
	GPIO.add_event_detect(18, GPIO.FALLING, callback=showNextDisplay, bouncetime=300)
	time_stamp = time.time()

	while 1:
		now = time.time()

		if  now > lastupdate + updateRate:
			RenderThread(tlocations[index]).start()
			lastupdate = now
			logging.debug(' Next update %s + %s' % ( now, updateRate ))
		if (display == 1):
			RenderTimeThread().start()

		for event in pygame.event.get():
			if event.type == pygame.MOUSEBUTTONDOWN:
				print "screen pressed" #for debugging purposes
				pos = (pygame.mouse.get_pos() [0], pygame.mouse.get_pos() [1])
				print pos #for checking
				pygame.draw.circle(lcd, WHITE, pos, 2, 0) #for debugging purposes - adds a small dot where the screen is pressed
				showNextLocation(1)

		time.sleep(1)
finally:
		logging.info( "  Reset GPIO & Quit")
		# Reset GPIO settings
		GPIO.cleanup()
