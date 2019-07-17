#!/usr/bin/env python

'''
---------------------------------------------------------------------------------------------------------------
Simple REST server for Python (3). Built to be multithreaded.
---------------------------------------------------------------------------------------------------------------
* TO BE DONE: UPDATE DESCRIPTION HERE!
* Last change: aggregatedLoad content
@Version 0.0.1
                                           Storage4Grid EU Project
                                      Implementation of Economic Model service
                                          on server 130.192.86.144
Features:
* Map URI patterns using regular expressions
* Map any/all the HTTP VERBS (GET, PUT, DELETE, POST)
* All responses and payloads are converted to/from JSON for you
* Easily serve static files: a URI can be mapped to a file, in which case just GET is supported
* You decide the media type (text/html, application/json, etc.)
* Correct HTTP response codes and basic error messages
* ----------------------------------------------------------------------------------------------------------- *
                                              API Description:
  * Because of visibility permissions, these such APIs will be accessible only from VPN.
  * Consequently, the only ip-valid target will be the VPN one: 10.8.0.50
* Weather:
  * "http://10.8.0.50:18081/weather/{lat},{lon}/"
  * http://10.8.0.50:18081/weather/+90.00,-11.00/
* ----------------------------------------------------------------------------------------------------------- *
---------------------------------------------------------------------------------------------------------------
@Author Ligios Michele
@update: 2019-06-06
'''
# ------------------------------------------------------------------------------------ #
# Generic Libraries:
import sys, os, re, shutil, json

import urllib.request, urllib.parse, urllib.error
from urllib.request import urlopen

import http.server
from http.server import HTTPServer as BaseHTTPServer

import requests # Used to simplify redirection

import socketserver
from socketserver import ThreadingMixIn
# ------------------------------------------------------------------------------------ #
import datetime
from datetime import *

# ------------------------------------------------------------------------------------ #
import pysolar
import numpy as np
import pytz as tz
import pandas as pd
# ------------------------------------------------------------------------------------ #
import xmltodict
# ------------------------------------------------------------------------------------ #

# To find correct locations
import geopy
from geopy.geocoders import Nominatim

import codecs
# ------------------------------------------------------------------------------------ #
# EVA related
import calendar
import math

# ------------------------------------------------------------------------------------ #
# PLOT for debugging purposes:
# import matplotlib.pyplot as plt
# enablePrintsPlot = True


here    = os.path.dirname(os.path.realpath(__file__))
records = {}
# ------------------------------------------------------------------------------------ #
# Full Numpy array (Avoid compression of data)
np.set_printoptions(threshold=np.inf)

# ------------------------------------------------------------------------------------ #
# 		Global temporary flags to enable print logging:
# ------------------------------------------------------------------------------------ #
# 1. Enable Control Flow prints about main logic
# ------------------------------------------------------------------------------------ #
enablePrints         = False
# ------------------------------------------------------------------------------------ #
# 2. Enable Content results prints about Run-time evaluation
# ------------------------------------------------------------------------------------ #
enableResultsContent = False
# ------------------------------------------------------------------------------------ #
# 3. Enable Control Flow prints about HTTP Server
# ------------------------------------------------------------------------------------ #
enableHTTPPrints     = False
# ------------------------------------------------------------------------------------ #
# 4. Enable Time-Monitoring features to verify delays introduced by the HTTP server
# ------------------------------------------------------------------------------------ #
enableTimingEval     = False

# ----------------------------------------------------------------------------------- #
# PATH (files under a inner folder: EVstats)
EV_PREFIX     = str(here) + "/EVstats/"
MAX_EV_NUMBER = 99999
# The prediction made by the following API is always made respect the current day.
# The only exception is managed when the user set a weekday specific in the API.
# In the last case, it will be provided the forecast for that weekday!
# [Concerning a time window of months, the weekday prediction will be always the same]
# This is the reason behind the choise to avoid to put a specific day as a time prefix.
# http://10.8.0.50:18081/EVA/11
# http://10.8.0.50:18081/EVA/Monday
# 
def get_ev_profile(handler):
	words = handler.path

	if(enableTimingEval == True):
		start = datetime.utcnow()

	if(enablePrints == True):
		print("Start get_ev_profile")

	# In case userinput is a number it is related to the amount of EV to manage
	# In case userinput is "Today", then must be converted on the current day and then converted exploiting the inner file
	# In case userinput is a weekday, then must be converted exploiting the inner file
	userinput  = words.split("/")[2]

	weekFlag = False

	if(userinput.isdigit() == True):
		number_of_EVs = int(userinput)
	else:
		if(userinput == "Today"):
			model_input = calendar.day_name[datetime.now().weekday()]
		else:
			# Already valid because verified via regex
			model_input = userinput
			weekFlag = True

		weekday = model_input.capitalize()
		rdf = pd.read_csv(EV_PREFIX+'WEEK_DAYS_NUMBER.txt', header = None)
		rdf.columns = ['day', 'mean','sigma']

		num_mu, num_sigma = rdf[rdf['day'] == weekday]['mean'], rdf[rdf['day'] == weekday]['sigma']
		num_sigma /= 2
		number_of_EVs = abs(math.ceil(np.random.normal(num_mu, num_sigma, 1)[0]))

	if(enablePrints == True):
		print("userinput: " + str(userinput))
		print("number_of_EVs: " + str(number_of_EVs))
		print("Going to Read plugTime")


	if(number_of_EVs > MAX_EV_NUMBER):
		print("Number of EV too high (with current settings this API last too much time): ask michele.ligios@linksfoundation.com")
		return("Number of EV too high (with current settings this API last too much time): ask michele.ligios@linksfoundation.com")
	elif(number_of_EVs == 0):
		print("Number of EV inconsistent: zero EV?")
		return("Number of EV inconsistent: zero EV?")

	try:
		# the data so far have high standard deviation because of the trend .... To BE HANDLED later in a more elegant way!	
		##### reading probability distribution data from the dedicated file for plugging time 
		df_plug = pd.read_csv(EV_PREFIX+'plugTime', sep='	',  header='infer')
		df_plug.columns = ['Time','pdf']

		# tries to distribute fairely, with round or ceil the elements under zero are pushed towards either 0 or 1
		distr_factor = 1000 
		dist_list = [[i]*int(round(df_plug['pdf'][i] * distr_factor)) for i in list(df_plug.index)]
		dist_list = np.concatenate(dist_list)

		plugging_time = np.random.choice(dist_list, number_of_EVs)

		#number of EVS per every slot of 15 minutes
		num_per_slot = pd.DataFrame(np.zeros(len(df_plug['Time'].values)))
		df_x =  df_plug['Time'].values

		num_per_slot.index = df_plug['Time'][df_x].index
		num_per_slot.columns = ['EV per slot']
		
		vc = pd.Series(df_plug['Time'][plugging_time].index).value_counts()

		df_ = pd.DataFrame(list(vc.values), df_plug['Time'][list(vc.index)].values)
		num_per_slot.columns =['Number of vehicle to plug in']

		num_per_slot.values[vc.index.values.astype(int)] = df_.values


		# the EV_dict is a charing profile table for the entire fleet, containing "PLUGGING TIME", "PARKING DURATION" and "ENERGY NEEDED"
		EV_dict = {'EV'+str(i):{'plug_time':None,'energy_need':None,'park_duration':None,} for i in range(number_of_EVs)}
		for i in range(len(EV_dict.keys())):
		    EV_dict[list(EV_dict.keys())[i]]['plug_time'] = plugging_time[i]

	except Exception as e:
		if(enablePrints == True):
			print("S4G Service Error! plugTime Error! %s" %e)
		return str("S4G Service Error! plugTime Error! %s" %e) 


	if(enablePrints == True):
		print("Going to Read parking")


	try:
		##### reading data from "parking" probability distribution which distributes all the fleet within differnt time hours 
		df_ = None
		df_p = pd.read_csv(EV_PREFIX+'parking', sep='	',  header='infer')
		df_p = df_p.fillna(0)
		df_p.columns = ['Time','mu (hours)','sigma (hours)']

		for (i,j) in EV_dict.items():
		    mu = df_p['mu (hours)'][j['plug_time']]
		    sigma = df_p['sigma (hours)'][j['plug_time']]
		    p = np.random.normal(mu, sigma, 1)
		    EV_dict[i]['park_duration'] = abs(p)[0]

	except Exception as e:
		if(enablePrints == True):
			print("S4G Service Error! parking Error! %s" %e)
		return str("S4G Service Error! parking Error! %s" %e) 

	if(enablePrints == True):
		print("Going to Read energy")

	try:
		#### reading probability data for energy to be received by each EV
		df_ = None
		df_e = pd.read_csv(EV_PREFIX+'energy', sep='	',  header='infer')
		df_e = df_e.fillna(0)
		df_e.columns = ['Time', 'sigma (hours)', 'mu (hours)']
		
		# the power consumed estimation
		charging_levels = [3.5, 6, 10, 22]
		for (i,j) in EV_dict.items():
		    energy_mu = df_e['mu (hours)'][j['plug_time']]
		    energy_sigma = df_e['sigma (hours)'][j['plug_time']]
		    e = np.random.normal(energy_mu, energy_sigma, 1)
		    EV_dict[i]['energy_need'] = abs(e)[0]
		    if (EV_dict[i]['energy_need']/EV_dict[i]['park_duration'] > max(charging_levels)): EV_dict[i]['energy_need'] = EV_dict[i]['park_duration'] * max(charging_levels)	
		
	except Exception as e:
		if(enablePrints == True):
			print("S4G Service Error! energy Error! %s" %e)
		return str("S4G Service Error! energy Error! %s" %e) 
	
	if(enablePrints == True):
		print("Going to build DataFrame")

	EV_dict = pd.DataFrame(EV_dict)

	# the prediction horizon is two time of the requested because 
	# what remains after midnight for the next day would be added 
	# to the corresponding time of the current day  
	blank_array = np.zeros(2 * len(df_plug))
	sim_slot = 0.25 ### this says that simulation steps are in 15 minutes
	powers=[]
	for (i,j) in EV_dict.items():
		power = j['energy_need'] / j['park_duration']
		if power < 3.5:
			power=3.5
			active_charging_time = j['energy_need'] / power
		elif (power>3.5 and power<6):
			power=6
			active_charging_time = j['energy_need'] / power
		elif (power>6 and power<10):
			power=10
			active_charging_time = j['energy_need'] / power
		elif (power>10 and power<16):
			power=16
			active_charging_time = j['energy_need'] / power
		elif (power>16):
			power=22
			active_charging_time = j['energy_need'] / power
		powers.append(power)
		park_in_sim_slot = math.ceil(active_charging_time  / sim_slot)
		blank_array[int(j['plug_time']): int(j['plug_time'] + park_in_sim_slot)] += power 


	if(enablePrints == True):
		print("Going to build Array")

	flag = 0

	if not flag:
		flag +=1 
		blank_array[:int(len(blank_array) / 2)] += blank_array[int(len(blank_array) / 2):]
		blank_array = blank_array[:int(len(blank_array) / 2)]
		blank_array = pd.DataFrame(blank_array, columns=['EV Total Charging Profile'])	
		blank_array.index = df_plug['Time'].values
	try:

		if(enablePrints == True):
			print("JSON Conversion of results")
			print(type(blank_array.index))
			#print(blank_array.index)
			print(blank_array)


		# Required JSON conversion:
		final_results = blank_array.to_json()
		jsonString = final_results.replace('\\"',"\"")

		########################################################################
		# 2019-05-02 # JSON string to dictionary 
		# (parse again to provide different output format):
		mydict = json.loads(jsonString)
		if(enablePrints == True):
			print("JSON Results:")
			print(type(mydict))
			print(mydict)


		if(weekFlag == True):
			evaDay     = model_input
		else:
			evaDay     = datetime.utcnow().strftime('%d/%m/%Y')

		evaList    = []
		
		for z,w in mydict.items():
			# z is the title!
			# We can drop it!
			for x,y in w.items():
				# Then we iterate for each row (time) and we split it
				nestedElem = {}
				nestedElem['DateTime'] = str(evaDay)+ " " +str(x)
				nestedElem['EVs']      = y
				nestedElem['Unit']     = "KW"
				evaList.append(nestedElem)

		# print(evaList)
		########################################################################
		if(enableTimingEval == True):
			end = datetime.utcnow()
			print("[LOG] Generic get_ev_profile API last: " + str(end - start))

		return evaList
		# return json.loads(jsonString)

	except Exception as e:
		if(enablePrints == True):
			print("S4G Service Error! blank_array conversion error! %s" %e)
		return str("S4G Service Error! blank_array conversion error! %s" %e) 


# ------------------------------------------------------------------------------------ #
# 				HTTP REST SERVER
# ------------------------------------------------------------------------------------ #
# MULTI-THREAD IMPLEMENTATION:
class ThreadingHTTPServer(socketserver.ThreadingMixIn, BaseHTTPServer):
    pass

# ------------------------------------------------------------------------------------ #
def rest_call_json(url, payload=None, with_payload_method='PUT'):
	'REST call with JSON decoding of the response and JSON payloads'
	if payload:
		if not isinstance(payload, str):
        		payload = json.dumps(payload)

		req = urllib.request.Request(url)
		# PUT or POST
		response = urlopen(MethodRequest(url, payload, {'Content-Type': 'application/json'}, method=with_payload_method))
	else:
		# GET
		response = urlopen(url)

	response = response.read().decode()
	return json.loads(response)


class MethodRequest(urllib.request.Request):
	'See: https://gist.github.com/logic/2715756'
	def __init__(self, *args, **kwargs):
		if 'method' in kwargs:
			self._method = kwargs['method']
			del kwargs['method']
		else:
			self._method = None
		return urllib2.request.__init__(self, *args, **kwargs)


	def get_method(self, *args, **kwargs):
		return self._method if self._method is not None else urllib.request.Request.get_method(self, *args, **kwargs)

class RESTRequestHandler(http.server.BaseHTTPRequestHandler):
	def __init__(self, *args, **kwargs):
		self.routes = {
### Generic Prices (From transparency AREA-CODE-ID)
		r'^/GENERIC/[A-Za-z0-9\-]+/prices$': {'GET': get_prices, 'media_type': 'application/json'},
### Generic Prices (From latitude and longitude)
		# http://10.8.0.50:18081/{latitude},{longitude}/{type}/prices/
		# r'^/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-8][0-9]|90).\d+/[A-Za-z0-9\-]+/prices$': {'GET': get_prices_from_location, 'media_type': 'application/json'},
		# NOTE: [A-Za-z0-9\-]+ is not yet used! Future purposes [type of contract: commercial/residential]
		r'^/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-9][0-9]|1[0-8][0-9]|190).\d+/[A-Za-z0-9\-]+/prices$': {'GET': get_prices_from_location, 'media_type': 'application/json'},
		r'^/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-9][0-9]|1[0-8][0-9]|190).\d+/prices/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])$': {'GET': get_prices_complete, 'media_type': 'application/json'},
### Price & Grid
		r'^/EDYNA/commercial/prices$': {'GET': get_edyna_prices, 'media_type': 'application/json'},
		r'^/EDYNA/residential/aggregatedloads$': {'file': 'EDYNA/aggregated-Residential.json', 'media_type': 'application/json'},
### Generic Aggregated Loads (From latitude and longitude)
		# http://10.8.0.50:18081/{latitude},{longitude}/{type}/aggregatedloads 
		# r'^/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-8][0-9]|90).\d+/[A-Za-z0-9\-]+/aggregatedloads$': {'GET': get_load_from_location, 'media_type': 'application/json'},
		r'^/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-9][0-9]|1[0-8][0-9]|190).\d+/[A-Za-z0-9\-]+/aggregatedloads$': {'GET': get_load_from_location, 'media_type': 'application/json'},
# Residential
		r'^/EDYNA/grid$': {'file': 'EDYNA/grid.json', 'media_type': 'application/json'},
		r'^/EDYNA/lines$': {'file': 'EDYNA/lines.json', 'media_type': 'application/json'},
		r'^/EDYNA/linecodes$': {'file': 'EDYNA/linecodes.json', 'media_type': 'application/json'},
		r'^/EDYNA/loads$': {'file': 'EDYNA/loads.json', 'media_type': 'application/json'},
		r'^/EDYNA/loadshapes$': {'file': 'EDYNA/loadshapes.json', 'media_type': 'application/json'},
		r'^/EDYNA/nodes$': {'file': 'EDYNA/nodes.json', 'media_type': 'application/json'},
		r'^/EDYNA/PV_absorb_effs$': {'file': 'EDYNA/PV_absorb_effs.json', 'media_type': 'application/json'},
		r'^/EDYNA/PVs$': {'file': 'EDYNA/pvs.json', 'media_type': 'application/json'},
		r'^/EDYNA/PV_temp_effs$': {'file': 'EDYNA/PV_temp_effs.json', 'media_type': 'application/json'},
		r'^/EDYNA/source$': {'file': 'EDYNA/source.json', 'media_type': 'application/json'},
		r'^/EDYNA/storages$': {'file': 'EDYNA/storages.json', 'media_type': 'application/json'},
		r'^/EDYNA/substations$': {'file': 'EDYNA/substations.json', 'media_type': 'application/json'},
		r'^/EDYNA/transformers$': {'file': 'EDYNA/transformers.json', 'media_type': 'application/json'},
# Commercial
		r'^/EDYNA/commercial/evs$': {'file': 'EDYNA/commercial/evs.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/feeders$': {'file': 'EDYNA/commercial/feeders.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/lines$': {'file': 'EDYNA/commercial/lines.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/linecodes$': {'file': 'EDYNA/commercial/linecodes.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/loads$': {'file': 'EDYNA/commercial/loads.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/loadshapes$': {'file': 'EDYNA/commercial/loadshapes.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/nodes$': {'file': 'EDYNA/commercial/nodes.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/PVs$': {'file': 'EDYNA/commercial/pvs.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/source$': {'file': 'EDYNA/commercial/source.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/storages$': {'file': 'EDYNA/commercial/storages.json', 'media_type': 'application/json'},
		r'^/EDYNA/commercial/transformers$': {'file': 'EDYNA/commercial/transformers.json', 'media_type': 'application/json'},

### Price & Grid
		r'^/ENIIG/commercial/prices$': {'GET': get_eniig_prices, 'media_type': 'application/json'},
		r'^/ENIIG/commercial/aggregatedloads$': {'file': 'ENIIG/aggregated-loads.json', 'media_type': 'application/json'},
		r'^/ENIIG/grid$': {'file': 'ENIIG/grid.json', 'media_type': 'application/json'},
		r'^/ENIIG/lines$': {'file': 'ENIIG/lines.json', 'media_type': 'application/json'},
		r'^/ENIIG/linecodes$': {'file': 'ENIIG/linecodes.json', 'media_type': 'application/json'},
		r'^/ENIIG/loadshapes$': {'file': 'ENIIG/loadshapes.json', 'media_type': 'application/json'},
		r'^/ENIIG/loads$': {'file': 'ENIIG/loads.json', 'media_type': 'application/json'},
		r'^/ENIIG/nodes$': {'file': 'ENIIG/nodes.json', 'media_type': 'application/json'},
		r'^/ENIIG/PV_absorb_effs$': {'file': 'ENIIG/PV_absorb_effs.json', 'media_type': 'application/json'},
		r'^/ENIIG/PVs$': {'file': 'ENIIG/pvs.json', 'media_type': 'application/json'},
		r'^/ENIIG/PV_temp_effs$': {'file': 'ENIIG/PV_temp_effs.json', 'media_type': 'application/json'},
		r'^/ENIIG/source$': {'file': 'ENIIG/source.json', 'media_type': 'application/json'},
#		r'^/ENIIG/storages$': {'file': 'ENIIG/storages.json', 'media_type': 'application/json'},
#		r'^/ENIIG/substations$': {'file': 'ENIIG/substations.json', 'media_type': 'application/json'},
		r'^/ENIIG/transformers$': {'file': 'ENIIG/transformers.json', 'media_type': 'application/json'},

		# http://10.8.0.50:18081/weather/{lat},{lon}/
		# r'^/weather/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-8][0-9]|90).\d+/$': {'GET': get_weather, 'media_type': 'application/json'},
		r'^/weather/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-9][0-9]|1[0-8][0-9]|190).\d+/$': {'GET': get_weather, 'media_type': 'application/json'},
### EVA (profiles) |[0-9][0-9]
		r'^/EVA/(([0-9]+)|(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Today))$': {'GET': get_ev_profile, 'media_type': 'application/json'},
### PV 
		# http://10.8.0.50:18081/pv/{date_from}/{date_to}/{lat},{lon}/{tilt}/{horizon_declination}/
		# r'^/pv/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-8][0-9]|90).\d+/[+]?([0-9]|[0-9][0-9]|1[0-7][0-9]|180)/[-+]?([0-9]|[0-8][0-9]|90)/$': {'GET': get_precise_pv, 'media_type': 'application/json'},
		# r'^/pv/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-8][0-9]|90).\d+/$': {'GET': get_pv, 'media_type': 'application/json'}}
		r'^/pv/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-9][0-9]|1[0-8][0-9]|190).\d+/[+]?([0-9]|[0-9][0-9]|1[0-7][0-9]|180)/[-+]?([0-9]|[0-8][0-9]|90)/$': {'GET': get_precise_pv, 'media_type': 'application/json'},
		r'^/pv/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/20[0-9][0-9](\.|-)(0[1-9]|1[0-2])(\.|-)(0[1-9]|1[0-9]|2[0-9]|3[0-1])/[-+]?([0-9]|[0-8][0-9]|90).\d+,[-+]?([0-9]|[0-9][0-9]|1[0-8][0-9]|190).\d+/$': {'GET': get_pv, 'media_type': 'application/json'}}

### Hybrid
### EVA (RT)
### EVA (Historical)
# EXAMPLES FOR PUT / POST / DELETE
#		r'^/records$': {'GET': get_records, 'media_type': 'application/json'},
#		r'^/record/': {'GET': get_record, 'PUT': set_record, 'DELETE': delete_record, 'media_type': 'application/json'}}        
		return http.server.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)


	def do_HEAD(self):
		self.handle_method('HEAD')
    
	def do_GET(self):
		self.handle_method('GET')

	def do_POST(self):
		self.handle_method('POST')

	def do_PUT(self):
		self.handle_method('PUT')

	def do_DELETE(self):
		self.handle_method('DELETE')
    
	def get_payload(self):
		payload_len = int(self.headers.getheader('content-length', 0))
		payload = self.rfile.read(payload_len)
		payload = json.loads(payload)
		return payload

        # HTTP Response Method:
	def handle_method(self, method):		
		if(enableHTTPPrints == True):
			print("[LOG] handle_method START")

		route = self.get_route()
		if route is None:
			if(enableHTTPPrints == True):
				print("[LOG] route None")
			self.send_response(404)
			self.end_headers()
			# The following case should be very fast
			# That's why should not be required a dedicated try catch
			# to manage clients that disconnects before receiving responses
			self.wfile.write('Route not found\n'.encode('UTF-8'))
		else:
			if(enableHTTPPrints == True):
				print("[LOG] route: " + str(route))
			if method == 'HEAD':
				self.send_response(200)
				if 'media_type' in route:
					self.send_header('Content-type', route['media_type'])
				self.end_headers()
			else:
				if 'file' in route:
					if(enableHTTPPrints == True):
						print("[LOG] File Request!")

					if method == 'GET':
						if(enableHTTPPrints == True):
							print("[LOG] GET Request Recognized!")
						try:
							f = open(os.path.join(here, route['file']), 'rb')
							if(enableHTTPPrints == True):
								print("[LOG] File opened!")
							try:
								self.send_response(200)
								if(enableHTTPPrints == True):
									print("[LOG] Response sent!")

								if 'media_type' in route:
									self.send_header('Content-type', route['media_type'])
								self.end_headers()
								if(enableHTTPPrints == True):
									print("[LOG] Headers closed!")
								shutil.copyfileobj(f, self.wfile)
								if(enableHTTPPrints == True):
									print("[LOG] File object copy ended!")
							finally:
								# The following case should be very fast
								# That's why should not be required a dedicated try catch
								# to manage clients that disconnects before receiving responses
								f.close()
						except Exception as e:
							if(enableHTTPPrints == True):
								print("[LOG] Raised Exception! (Missing file?) %s " %e)
							self.send_response(404)
							self.end_headers()
							self.wfile.write('File not found\n'.encode('UTF-8'))
					else:
						if(enableHTTPPrints == True):
							print("[LOG] NoN-GET Request Recognized!")
						self.send_response(405)
						self.end_headers()
						# The following case should be very fast
						# That's why should not be required a dedicated try catch
						# to manage clients that disconnects before receiving responses
						self.wfile.write('Only GET is supported\n'.encode('UTF-8'))
				else:
					if(enableHTTPPrints == True):
						print("[LOG] Method Request!")
					try:
						if method in route:
							if(enableHTTPPrints == True):
								print("[LOG] Request in Known Routes!")
							content = route[method](self)
							if content is not None:
								if(enableHTTPPrints == True):
									print("[LOG] Request content not None!")

								self.send_response(200)
								if 'media_type' in route:
									self.send_header('Content-type', route['media_type'])
								self.end_headers()
								if method != 'DELETE':
		                        				self.wfile.write(json.dumps(content).encode('UTF-8'))
							else:
					                    self.send_response(404)
					                    self.end_headers()
		                			    self.wfile.write('Not found\n'.encode('UTF-8'))
						else:
							self.send_response(405)
							self.end_headers()
							self.wfile.write(method + ' is not supported\n'.encode('UTF-8'))
					except Exception as e:
						print("[LOG] Raised Exception! (Client disconnected badly): %s" %e)
                    
# ------------------------------------------------------------------------------------ #    
# Find out which APIs to dispatch
	def get_route(self):
		for path, route in list(self.routes.items()):
			if re.match(path, self.path):
				return route
		return None

# Start REST server 
# ------------------------------------------------------------------------------------ #
def rest_server(server_class=ThreadingHTTPServer, handler_class=RESTRequestHandler):
	'Starts the REST server'
	ip   = '0.0.0.0'
	port = 18081

	# Multi-threaded
	http_server = server_class((ip, port),handler_class)

	# Single-threaded
	#http_server = http.server.HTTPServer((ip, port), RESTRequestHandler)

	print(('Starting MT HTTP server at %s:%d' % (ip, port)))
	try:
        	http_server.serve_forever()
	except KeyboardInterrupt:
		pass
	print('Stopping HTTP server')
	http_server.server_close()

def main(argv):
	print((sys.version_info))
	rest_server()

if __name__ == '__main__':
	main(sys.argv[1:])

def get_records(handler):
	return records

def get_record(handler):
	key = urllib.parse.unquote(handler.path[8:])
	return records[key] if key in records else None

def set_record(handler):
	key = urllib.parse.unquote(handler.path[8:])
	payload = handler.get_payload()
	records[key] = payload
	return records[key]

def delete_record(handler):
	key = urllib.parse.unquote(handler.path[8:])
	del records[key]
	return True # anything except None shows success

