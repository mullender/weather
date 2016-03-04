import time

"""
Parses aculink post data
Mostly copied from hackulink code found here: http://geekfun.com/hackulink/

Other useful info:
http://moderntoil.com/?p=794
http://nincehelser.com/ipwx/
https://groups.google.com/forum/#!msg/weewx-user/G8RU514qndk/4E8p_hLUwtYJ
"""


class AcuLink:
    def __init__(self):
        pass

    def can_handle(self, url, data):
        return url == "http://www.acu-link.com/messages/" and data.startswith("id=")

    def handle(self, url, data):
        return self._process_message(data)

    def _process_message(self, message):
        _packet = {}

        # separate line into a dict
        _l = message.split('&')
        _d = dict([i.split('=') for i in _l])

        if _d['mt'] == "pressure":
            _packet.update(self._barometer_reading(_d))
        elif _d['mt'] != "tower":
            for _k, _v in _d.items():
                if _k in AcuLink._dispatch_dict:
                    _packet.update([AcuLink._dispatch_dict[_k](self, _v)])

        # calculate derived values
        if _d['mt'] == "5N1x38":

            T = _packet['outTemp']
            R = _packet['outHumidity']
            W = _packet['windSpeed']

            # _packet['dewpoint']  = weewx.wxformulas.dewpointC(T, R)
            # _packet['heatindex'] = weewx.wxformulas.heatindexC(T, R)
            # _packet['windchill'] = weewx.wxformulas.windchillC(T, W)

        elif _d['mt'] == "5N1x31":
            # Don't record a wind direction if windspeed is below 2kmh
            if _packet['windSpeed'] < 2.0:
                _packet['windDir'] = None

        # set timestamp and units
        _packet['dateTime'] = int(time.time())
        # _packet['usUnits'] = weewx.METRIC
        return _packet

    def _rain_reading(self, reading):
        # example: A0000254
        # measured rainfall in mm/1000 since last reading
        # 36s reporting interval

        # rainRate [in, cm]_per_hour
        # return ( 'rainRate', None ) # TODO Not doing anything with this yet, because it requires historical data
        return ('rain', float(reading[2:]) / 10000)

    def _temperature_reading(self, reading):
        # example: A018000000
        # index 1 : = 0 for positive, - for negative
        # index 2-10 temp in C with a decimal before the last digit
        # 36s reporting interval

        t = float(reading[2:10]) / 1000000
        if reading[1] == '-':
            t = -1 * t
        # outTemp: degree_[F, C]
        return ('outTemp', t)

    def _humidity_reading(self, reading):
        # input example: A0590
        # index 1-5 humidity % , with a decimal before the last.
        # 36s reporting interval

        # outHumidity: percent
        return ('outHumidity', float(reading[2:5]) / 10)

    def _windspeed_reading(self, reading):
        # example A000970000
        # index 2-6 speed in centimeters per second
        # 18s reporting interv

        # windSpeed: kmh
        return ('windSpeed', (float(reading[2:6]) * (60 * 60) / (1000 * 100)))

    def _winddir_reading(self, reading):
        # example: A
        # A single HEX digit. Assumption that 0=N
        # shouldn't be populated when there is low/no wind
        # 36s reporting interval

        # windDir: degree_compass
        return ('windDir', AcuLink._windmap_dict[reading])

    def _battery_reading(self, reading):
        # example: normal

        # txBatteryStatus
        return ('txBatteryStatus', int(reading == 'normal'))
        # return ( 'txBatteryStatus', None )

    def _rssi_reading(self, reading):
        # ranges from 0 to 4

        # rxCheckPercent: percent (may not be valid for loop packets)
        return ('rxCheckPercent', int(reading) * 25)
        # return ( 'rxCheckPercent', None )

    def _barometer_reading(self, reading):
        # example id=24C86E010EAD&mt=pressure&C1=4978&C2=0E3F&C3=0148&C4=03B5&C5=80F4&C6=1744&C7=09C4&A=07&B=15&C=06&D=09&PR=9C7E&TR=7F0B
        # Believed to be this formulae: http://www.hoperf.com/upload/sensor/HP03S.pdf
        # Programming Guide: http://www.hoperf.com/upload/sensor/HP03_code.pdf
        #
        #   Example
        #       Key     Value   Range (Hex)             Range(Dec)
        #       ---     -----   ---------------         -------------
        #       A:      07      0x01 -- 0x3F             1 -- 63
        #       B:      15      0x01 -- 0x3F             1 -- 63
        #       C:      06      0x01 -- 0x0F             1 -- 15
        #       C1:     4978    0x100 -- 0xFFFF          256 -- 65535
        #       C2:     0E3F    0x00  -- 0x1FFF          0   -- 8191
        #       C3:     0148    0x00 -- 0x400            0   -- 3000
        #       C4:     03B5    0x00 -- 0x1000           0   -- 4096
        #       C5:     80F4    0x1000 -- 0xFFFF        4096 -- 65535
        #       C6:     1744    0x00 -- 0x4000           0   -- 16384
        #       C7:     09C4    0x960 -- 0xA28          2400 -- 2600
        #       D:      09      0x01 -- 0x0F             1 -- 15
        #       PR:     9C7D    0x00 -- 0xFFFF           0 -- 65535
        #       TR:     7F0F    0x00 -- 0xFFFF           0 -- 65535


        A, B, C, C1, C2, C3, C4, C5, C6, C7, D, D1, D2 = [int(reading[i], 16) for i in ("A", "B", "C", "C1", "C2",
                                                                                        "C3", "C4", "C5", "C6",
                                                                                        "C7", "D", "PR", "TR")]

        if D2 >= C5:
            COEF = A
        else:
            COEF = B

        dUT = D2 - C5 - ((D2 - C5) / 2 ** 7) * ((D2 - C5) / 2 ** 7) * COEF / 2 ** C
        OFF = (C2 + (C4 - 1024) * dUT / 2 ** 14) * 4
        SENS = C1 + C3 * dUT / 2 ** 10
        X = SENS * (D1 - 7168) / 2 ** 14 - OFF
        P = (X * 10 / 2 ** 5) + C7
        T = 250 + (dUT * C6 / 2 ** 16) - dUT / 2 ** D

        # divide by ten because the formulas given seem to be fixed point
        # Not bothering with correcting this, for now.
        return [('barometer', P / 10.0), ('pressure', P / 10.0), ('inTemp', T / 10.0)]

    # Dictionary that maps a measurement code, to a function that can decode it:
    _dispatch_dict = {'rainfall': _rain_reading,
                      'temperature': _temperature_reading,
                      'pressure': _barometer_reading,
                      'humidity': _humidity_reading,
                      'windspeed': _windspeed_reading,
                      'winddir': _winddir_reading,
                      'battery': _battery_reading,
                      'rssi': _rssi_reading}

    # dictionary for decoding wind direction
    _windmap_dict = {'5': 0.0,
                     '7': 22.5,
                     '3': 45.0,
                     '1': 67.5,
                     '9': 90.0,
                     'B': 112.5,
                     'F': 135.0,
                     'D': 157.5,
                     'C': 180.0,
                     'E': 202.5,
                     'A': 225.0,
                     '8': 247.5,
                     '0': 270.0,
                     '2': 292.5,
                     '6': 315.0,
                     '4': 337.5}
