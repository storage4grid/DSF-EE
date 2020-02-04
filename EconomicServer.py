#!/usr/bin/env python
# Copyright 2019 Ligios Michele <michele.ligios@linksfoundation.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''
* ------------------------------------------------------------------------------------------------- *
* !!!WARNING ABOUT DEVELOPMENT!!!
* ------------------------------------------------------------------------------------------------- *
* When the current software is run by uWSGI the main() is not executed! 
* This is because the uWSGI load balancer trigger directly the flask APIs!
* Then, it is important to remember that by exploiting its multi-process management,
* there will be multiple instances running!
* Consequently, a configuration phase (i.e. mqtt client setup),
* it will affect only the current active process!
* In order to manage properly each instance, it is mandatory, 
* to control the initialization of every component on every API callback.
*
* ------------------------------------------------------------------------------------------------- *
* !!!WARNING ABOUT DEPLOYMENT!!!
* ------------------------------------------------------------------------------------------------- *
* Remember that, by building the new docker image you will override the persistence SQlite Database!
* In order to mantains the previously stored data, before compiling it again, you have to manually:
* Copy from the dedicated volume the updated Database on the EconomicServer folder
* (Overriding the starting one)
* Then you can safely re-build and re-start it.
*
* ------------------------------------------------------------------------------------------------- *
* !!!UPDATES!!!
* ------------------------------------------------------------------------------------------------- *
* Fixed API endpoints
*
* ------------------------------------------------------------------------------------------------- *
* !!! BUILD INSTRUCTIONS !!!
* ------------------------------------------------------------------------------------------------- *
* sudo docker build . -t economicserverimage
*
* BASE:
* sudo docker run --name economicserver -p 9082:9081 -d economicserverimage
*
* Obtain certificates first (DEPRECATED, it exploits old authentication mechanism):
* sudo docker run --rm -it -v "/root/letsencrypt/log:/var/log/letsencrypt" -v "/var/www/html/shared:/var/www/" -v "/etc/letsencrypt:/etc/letsencrypt" -v "/root/letsencrypt/lib:/var/lib/letsencrypt" lojzik/letsencrypt certonly --webroot --webroot-path /var/www --email michele.ligios@linksfoundation.com -d dwh.storage4grid.eu
*
* Renew certificates (DEPRECATED, it exploits old authentication mechanism):
* sudo docker run --rm -v "/root/letsencrypt/log:/var/log/letsencrypt" -v "/var/www/html/shared:/var/www/" -v "/etc/letsencrypt:/etc/letsencrypt" -v "/root/letsencrypt/lib:/var/lib/letsencrypt" lojzik/letsencrypt renew
*
* Cron rule to renew certificates:
* 0 0 * * * docker run --rm -v "/root/letsencrypt/log:/var/log/letsencrypt" -v "/var/www/html/shared:/var/www/" -v "/etc/letsencrypt:/etc/letsencrypt" -v "/root/letsencrypt/lib:/var/lib/letsencrypt" lojzik/letsencrypt renew >> /var/log/certbot.log 2>&1 && service nginx reload >> /var/log/certbot.log 2>&1
*
*
* ADVANCED (VOLUMES with Certificates):
* sudo docker run --name economicserver -v "/root/letsencrypt/log:/var/log/letsencrypt" -v "/var/www/html/shared:/var/www/" -v "/etc/letsencrypt:/etc/letsencrypt" -v "/root/letsencrypt/lib:/var/lib/letsencrypt" -p 9082:9081 -d economicserverimage
*
* CERTIFICATES GENERATION (CN value must be the same as for the FDQN)
* sudo openssl req -x509 -nodes -days 565 -newkey rsa:2048 -keyout /etc/ssl/private/nginx-selfsigned.key -out /etc/ssl/certs/nginx-selfsigned.crt
* 
* ------------------------------------------------------------------------------------------------- *
* !!! DEBUG INSTRUCTIONS !!!
* ------------------------------------------------------------------------------------------------- *
* Show certificate property
* curl -k -v https://ip:9082/
* curl --insecure -v https://www.google.com 2>&1 | awk 'BEGIN { cert=0 } /^\* Server certificate:/ { cert=1 } /^\*/ { if (cert) print }'
* curl --cacert mycompany.cert  https://www.mycompany.com
* ------------------------------------------------------------------------------------------------- *
* !!! DETAILS !!!
* ---------------------------------------------------------------------------------------------------------------
* Simple REST server for Python (3). Built to be multithreaded together with nginx and uwsgi.
* ---------------------------------------------------------------------------------------------------------------
* @Version 1.1.2
*                                           Storage4Grid EU Project
*                                      Implementation of Economic Server Connector
* @Notes:
* ---------------------------------------------------------------------------------------------------------------
* The current Backend will interact with Professional GUI and with the DSF-SE to:
* - receive Professional GUI and DSF-SE inputs.
* - evaluate the economic model scenario.
* - store persistently the information of interest. JSON File for debug and DB: sqlite3
* - forward the economic results back to the Professional GUI
* ---------------------------------------------------------------------------------------------------------------
* It is built in the following context:
* - Public IP                 
* - HTTPS only APIs          (nginx settings)
* - self-signed certificates (openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365)
* ---------------------------------------------------------------------------------------------------------------
* In order to satisfy the security requirements to prevent cyber-attacks,
* it has been built in python exploiting Flask together with:
* - nginx
* - uwsgi
* ---------------------------------------------------------------------------------------------------------------
* It is installed as a systemctl service.
* It is run with the following base-settings:
* # uwsgi --http-socket :9090 --plugin python --wsgi-file foobar.py
* It is run with the following good-settings:
* # uwsgi --http-socket :9090 --plugin python --wsgi-file foobar.py
* It is run with the following best-settings (exploting a configuration file):
* # uwsgi --ini myproject.ini
* ---------------------------------------------------------------------------------------------------------------
* @OtherNotes:
* If you want to run Flask in production, 
* be sure to use a production-ready web server like Nginx, 
* and let your app be handled by a WSGI application server like Gunicorn/uWSGI.
* https://uwsgi-docs.readthedocs.io/en/latest/WSGIquickstart.html
* https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-uswgi-and-nginx-on-ubuntu-18-04
* ---------------------------------------------------------------------------------------------------------------
* @Features exposed towards Professional GUI & DSF-SE:
* -POST- https://dwh.storage4grid.eu:9082/EE/input
* ---------------------------------------------------------------------------------------------------------------
* Following APIs are all REST GET:
* TESTING PURPOSES:
* - https://10.8.0.50:9082/
* ---------------------------------------------------------------------------------------------------------------
* @Author: Ligios Michele
* @Created: 2019-06-11
* @Updated: 2019-07-17
* @update final
'''
# ------------------------------------------------------------------------------------ #
# Generic Libraries:
import sys, os, re, shutil, json
# ------------------------------------------------------------------------------------ #
from flask import Flask, request
# ------------------------------------------------------------------------------------ #
import configparser
import time
import sqlite3
import datetime

# ------------------------------------------------------------------------------------ #
# Import libraries in lib directory
base_path = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(base_path, 'lib'))
# ------------------------------------------------------------------------------------ #
# ------------------------------------------------------------------------------------ #
# * Serving Flask app "EconomicServer" (lazy loading)
# * Environment: production
#   WARNING: Do not use the development server in a production environment.
#   Use a production WSGI server instead.
# * Debug mode: on
# * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
# * Restarting with stat
# ------------------------------------------------------------------------------------ #
# To enable CROSS-ORIGIN Requests (CORS): 09/2019
from flask_cors import CORS
# Original Flask run
app = Flask(__name__)
# Enable CORS
CORS(app)
# ------------------------------------------------------------------------------------ #
# VERIFY VERY WELL THE FOLLOWING FLAGS BEFORE BUILDING!
localDebugHTTP   = False        # Required for building local python app (not inside docker) in HTTP or HTTPS
# ------------------------------------------------------------------------------------ #
enablePrints     = True
enableFullPrints = False
enableFulldebug  = True
# ------------------------------------------------------------------------------------ #
@app.route("/")
def home():
	return "Economic Server Reached!"
# ------------------------------------------------------------------------------------ #
# FIXED PARAMETERS (Previously evaluated):
# ------------------------------------------------------------------------------------ #
# Prudent average rate for decreasing  battery price (%):
prudentAverageBatteries = -7.16/100
# ------------------------------------------------------------------------------------ #
# Regression parameters:
a0 = 24.426
a1 = 2994.1
a2 = -90.806
a3 = 0.8923
a4 = -0.0027
# ------------------------------------------------------------------------------------ #
# Rescaled Regression parameters:
b0 = a0 - 7000
b1 = a1
b2 = a2
# ------------------------------------------------------------------------------------ #
# Range of allowded values for kwp (required to define the PV penetration %):
KWpMax = 150
Econsumption = [2500,1200,2500,800] # Deprecated (indifferente rispetto allo scenario)

# EconsumptionCost = Econsumption[ScenarioID] * Pen (DEPRECATED)
# EconsumptionCost_PV = Econsumption[location]_PV * Pen
# EconsumptionCost_without_PV = Econsumption[location]_without_PV * Pen  
EconsumptionCost_PV         = 0
EconsumptionCost_without_PV = 0

# ------------------------------------------------------------------------------------ #
# These values Must be shared among the Scenarios:
# Percentage of shared Power Loss (50%)
pSharedPLoss = 0.5
# R Percentage (7%): 
r = 0.07
# ------------------------------------------------------------------------------------ #
# Generic values (DEPRECATED)
# Price energy:
# Pen = 0.31
Pen = 0
# Number of Households:
# nhouse = 15
nhouse = 0
# nhouse = 20
# Fixed cost amount (Scenario1):
# fixed_cost = 9000 # Deprecated
fixed_cost = 0

# Burocracy change based on scenario (instead of country)
# real_burocracy_cost = (290,6 * ESS_avg_capacity_res)*num_ess_res + (290,6 * ESS_avg_capacity_sub)*num_ess_sub
burocracy = 290.6
# ------------------------------------------------------------------------------------ #
# Legend:
# CF = Cash Flow
# PV = Present Value
# ------------------------------------------------------------------------------------ #
# Minimum years to be considered for an economical simulation
# simulationThreshold = 5 (DEPRECATED)
# ------------------------------------------------------------------------------------ #
# Updated pilot-specific values (Italy):
# Price energy:
penIt = 0.21
# Number of Households:
nhouseIt = 21
# Fixed cost amount:
# fixed_costIt = 9000 # Deprecated
# ------------------------------------------------------------------------------------ #
# Average of Power Consumption (Italy):
# EconsumptionIt = avgP_house_pvIt * nhousePvIt + avgP_house_WithoutpvIt * nhouseWithoutPvIt
# A seconda del valore del PV penetration nella offline simulation
# calcolo avgP_house_pvIt interpolando i valori di ogni scenario
# Senza PV per IT: consumo medio: 
# Con PV: 
avgP_house_pvIt        = 0
avgP_house_WithoutpvIt = 0
EconsumptionIt         = 0

# ------------------------------------------------------------------------------------ #
# Updated pilot-specific values (Denmark):
# Price energy:
penDk = 0.31
# Number of Households:
nhouseDk = 15
# Fixed cost amount:
# fixed_costDk = 9000 # Deprecated
# Average of Power Consumption:
# EconsumptionDk = avgP_house_pvDk * nhousePvDk + avgP_house_WithoutpvDk * nhouseWithoutPvDk 
# Senza PV per Fur: consumo medio: 5218
# Con PV: 1750
avgP_house_pvDk        = 1750
avgP_house_WithoutpvDk = 5218
EconsumptionDk         = 0
# ------------------------------------------------------------------------------------ #
yearly_tco             = 0
# ------------------------------------------------------------------------------------ #
debugExtension = ".json"
# ------------------------------------------------------------------------------------ #
# Allowed Scenario: [0,1,2,3]
scenarioDescription = ["Scenario 0: Traditional Grid Strengthening (Baseline)",\
			"Scenario 1: Decentralized Storage at household level",\
			"Scenario 2: Centralized Storage at Sub-station level",\
			"Scenario 3: Both centralized and decentralized storage"]
# ------------------------------------------------------------------------------------ #
kwp     = 0
pLoss   = 0
nss     = 0
CPwLoss = 0
# ------------------------------------------------------------------------------------ #
#  YEAR  | SIMULATED DATA (DOLLARS) |  SIMULATED DATA (EURO) 
simulatedBatteryData = [[2014,1331,1185],\
			[2015,1236,1100],\
			[2016,1147,1021],\
			[2017,1065,948],\
			[2018,989,880],\
			[2019,918,817],\
			[2020,852,758],\
			[2021,791,704],\
			[2022,734,654],\
			[2023,682,607],\
			[2024,633,563],\
			[2025,588,523],\
			[2026,546,486],\
			[2027,507,451],\
			[2028,470,419],\
			[2029,437,389],\
			[2030,405,361]]

# ------------------------------------------------------------------------------------ #
# Example of Message (Scenario 0):
# {
#  "Simulation": 0,
#  "Type": "oneShot",
#  "Info":
#   {
#     "SimulationTime": 10,
#     "kwp": 100,
#     "PLoss": 20,
#     "Nss": 0,
#     "BatteryList":
#     [      
#     ]
#   }
# }
# ------------------------------------------------------------------------------------ #
# Example of Message (Scenario 1):
# {
#  Simulation: 1,
#  Type: "oneShot",
#  Info:
#   {
#     SimulationTime: 10,
#     kwp: 100,
#     PLoss: 20,
#     Nss: 1000,
#     BatteryList:
#     [
#       {
#         BatteryID: "A",
#         Capacity:  10,
#         LifeTime:  20,
#         Position:  "Residential"
#       },
#       {
#         BatteryID: "B",
#         Capacity:  80,
#         LifeTime:  30,
#         Position:  "SubStation"
#       }
#     ]
#   }
# }
# ------------------------------------------------------------------------------------ #
@app.route("/EE/input",methods=['POST'])
def startEconomicEvaluation():
	# ----------------------------------- #
	DSO_CF      = []
	DSO_PV      = []
	PROSUMER_CF = []
	PROSUMER_PV = []
	timeArray   = []
	batteryList = []
	# ----------------------------------- #
	simulationTimeUpdate = 0
	# ----------------------------------- #
	residential_EssCapacity = 0
	residential_EssLifetime = 0
	dso_EssCapacity = 0
	dso_EssLifetime = 0
	# ----------------------------------- #
	description = "[EconomicServer][HTTPS][POST] Economic Model Evaluation"
	if(enablePrints == True):
		print(str(description))
	# ----------------------------------- #
	# Receive and parse
	try:					
		req_data      = request.get_json() 

		if(enableFulldebug == True):
			timestr = time.strftime("%Y%m%d-%H%M%S")
			# -------------------------------------------------------------------------------------------------- #
			# IMPROVED DEBUG:
			# Verify if already exists (should not because time in current date)
			# In case of fast request (more than one per second) it will overwrite the file.
			# -------------------------------------------------------------------------------------------------- #
			pathFile = "./startEEJsonDebug"+str(timestr)+str(debugExtension)
			exists = os.path.isfile(pathFile)
			counter = 0
			while exists:
				counter +=1				
				# Store configuration file values
				pathFile = "./startEEJsonDebug"+str(timestr)+"_"+str(counter)+str(debugExtension)
				exists = os.path.isfile(pathFile)
			# -------------------------------------------------------------------------------------------------- #
			with open(pathFile, 'w') as outfile:  
				json.dump(req_data, outfile)

		# -------------------------------------------------------------------------------------------------- #
		idSimulation        = req_data['simulation_id']
		locationSimulation  = req_data['grid_name'].lower()
		# ---------------------------------------------------------- #
		simulationTime      = req_data['simulation_time']
		# ---------------------------------------------------------- #
		nhousePV            = req_data['houses_with_pv']
		houses_without_pv   = req_data['houses_without_pv']
		# ---------------------------------------------------------- #
		kwp                 = req_data['kwp']
		pLoss               = req_data['kwh_losses']
		batteryList         = req_data['ESS_info']
		# ---------------------------------------------------------- #
		# FURTHER CONTROLS ABOUT GIVEN INPUTS:
		# ---------------------------------------------------------- #
		# Numerical Input validation:
		# ---------------------------------------------------------- #
		if(isinstance(batteryList, list) != True):
			raise ValueError('Wrong Input! ESS_info must be a list!')			
		nss = len(batteryList) 
		if(isinstance(nhousePV, (int)) != True):
			raise ValueError('Wrong Input! houses_with_pv must be a number!')
		if(isinstance(houses_without_pv, (int)) != True):
			raise ValueError('Wrong Input! houses_without_pv must be a number!')
		if(isinstance(kwp, (int, float, complex)) != True):
			raise ValueError('Wrong Input! kwp must be a number!')
		if(kwp > KWpMax):
			raise ValueError('Given kwp value is too high! [' +str(kwp) +']>['+str(KWpMax)+']')
		if(isinstance(simulationTime, (int)) != True):
			raise ValueError('Wrong Input! simulationTime must be a number!')			
		if(isinstance(pLoss, (int, float, complex)) != True):
			raise ValueError('Wrong Input! kwh_losses must be a number!')			
		if(isinstance(nss, (int, float, complex)) != True):
			raise ValueError('Wrong Input! inherited number of ESS must be a number!')			

		# ---------------------------------------------------------- #
		if(int(simulationTime) < 1):
			raise ValueError('Wrong Input! Simulation Time lower Limit is 1 year')						


		# ---------------------------------------------------------- #
		# Need to calculate the PV penetration % (from kwp):
		pvPerc = (kwp/KWpMax)
		if(enableFullPrints == True):
			print("Request Received: content("+str(req_data) + ")")
			print("idSimulation: " + str(idSimulation))
			print("kwp    = "+str(kwp))
			print("pvPerc = "+str(pvPerc*100) + " %")

		# ---------------------------------------------------------- #
		# IF the INPUT will involve pvPerc instead of kwp
		# Then enable the following lines:
		# pvPerc         = infoSimulation['PVperc']
		# Need to calculate the kwp starting from the PV penetration %:
		# kwp = pvPerc*KWpMax
		# ---------------------------------------------------------- #
		# Analize the Given Batteries List to identify the Scenario:
		foundResidential = False
		foundSubstation  = False

		resCounter = 0
		dsoCounter = 0

		avg_res_EssCapacity = 0
		avg_res_EssLifetime = 0

		avg_dso_EssCapacity = 0
		avg_dso_EssLifetime = 0
		# ---------------------------------------------------------- #
		i = 0
		while( i < len(batteryList)):
			if(batteryList[i]['location'] == "household"):
				foundResidential = True

				residential_EssCapacity = batteryList[i]['kwh']
				residential_EssLifetime = batteryList[i]['lifetime']

				avg_res_EssCapacity += residential_EssCapacity
				avg_res_EssLifetime += residential_EssLifetime
				resCounter += 1

			elif(batteryList[i]['location'] == "substation"):
				foundSubstation  = True

				dso_EssCapacity = batteryList[i]['kwh']
				dso_EssLifetime = batteryList[i]['lifetime']

				avg_dso_EssCapacity += dso_EssCapacity
				avg_dso_EssLifetime += dso_EssLifetime
				dsoCounter += 1

			i += 1

		ScenarioID = -1

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer] S4G Service [Input] Error %s" %e)
		return str("[EconomicServer] S4G Service [Input] Error %s" %e)

	try:
		# ---------------------------------------------------------- #
		# Scenario 0: NumberESS = 0 and nss = 0
		# Scenario 1: NumberESS > 0 and nss > 0 and Position = Residential only
		# Scenario 2: NumberESS > 0 and nss > 0 and Position = Substation only
		# Scenario 3: NumberESS > 0 and nss > 0 and Position = Both
		# ---------------------------------------------------------- #
		now = datetime.datetime.now()
		year = now.year

		# if(len(batteryList) == 0 and nss == 0):
		if(nss == 0):
			ScenarioID = 0
			simulationTimeUpdate = 20
		# elif(len(batteryList) > 0 and nss > 0):
		elif(nss > 0):
			# Requried to find the proper row of BatteryCosts Structure:
			now = datetime.datetime.now()
			year = now.year

			if(enableFullPrints == True):
				print("simulatedBatteryData: ")
				print(simulatedBatteryData)

			# Extract the estimation built about the current year:
			elementRow = [x for x in simulatedBatteryData if x[0] == year]

			# Extract the proper value:
			battSimulCost = elementRow[0][2]
			if(enableFullPrints == True):
				print("BatterySimluatedCost: " +str(battSimulCost))

			if(foundResidential == True and foundSubstation == False):
				ScenarioID = 1
				# ------------------------------------------------------------- #
				avg_res_EssCapacity = avg_res_EssCapacity/resCounter
				avg_res_EssLifetime = avg_res_EssLifetime/resCounter
				residential_capexSize = battSimulCost*avg_res_EssCapacity
				simulationTimeUpdate  = avg_res_EssLifetime
				# ------------------------------------------------------------- #
			elif(foundResidential == False and foundSubstation == True):
				ScenarioID = 2
				# ------------------------------------------------------------- #
				avg_dso_EssCapacity = avg_dso_EssCapacity/dsoCounter
				avg_dso_EssLifetime = avg_dso_EssLifetime/dsoCounter
				dso_capexSize = battSimulCost*avg_dso_EssCapacity
				simulationTimeUpdate  = avg_dso_EssLifetime
				# ------------------------------------------------------------- #
			elif(foundResidential == True and foundSubstation == True):
				ScenarioID = 3
				# ------------------------------------------------------------- #
				avg_res_EssCapacity = avg_res_EssCapacity/resCounter
				avg_res_EssLifetime = avg_res_EssLifetime/resCounter
				avg_dso_EssCapacity = avg_dso_EssCapacity/dsoCounter
				avg_dso_EssLifetime = avg_dso_EssLifetime/dsoCounter
				# ------------------------------------------------------------- #
				residential_capexSize = battSimulCost*avg_res_EssCapacity
				dso_capexSize         = battSimulCost*avg_dso_EssCapacity
				# ------------------------------------------------------------- #
				avg_lifetimes = (avg_res_EssLifetime+avg_dso_EssLifetime)/2
				simulationTimeUpdate = avg_lifetimes
			else:
				if(enablePrints == True):
					print("[EconomicServer] S4G Service [Starting Simulation] Error")
				return str("[EconomicServer] S4G Service [Starting Simulation] Error (" + str(req_data) + ")")
		else:
			# --------------------------------------- #
			# It means:
			# (len(batteryList) < 0) or 
			# (len(batteryList) == 0 and nss > 0) or
			# (len(batteryList) == 0 and nss < 0) or
			# (len(batteryList)  > 0 and nss < 0)
			# All these combinations are not allowed!
			# --------------------------------------- #
			if(enablePrints == True):
				print("[EconomicServer] S4G Service [Starting Simulation] Input Parsing Error")
			return str("[EconomicServer] S4G Service [Starting Simulation] Input Parsing Error (" + str(req_data) + ")")

		if(enablePrints == True):
			print("[EconomicServer] Identified Scenario: " +str(ScenarioID))


		# ---------------------------------------------------------- #
		# Conversion of values from FIT GUI tecnical simulation
		# to Economic Model Timeframe of interest
		# From x days to 1 year:
		# ---------------------------------------------------------- #
		# TODO: IF IT IS NEEDED TO CONVERT PLOSS:
		# convertedPLoss = (pLoss*365)/simulationTime
		convertedPLoss = pLoss
		# ---------------------------------------------------------- #
		# Update simulation time exploited by EE with the AVG ESS lifetime
		# pLoss = convertedPLoss
		simulationTime = int(simulationTimeUpdate)
		# ---------------------------------------------------------- #
		# TODO: conversion of values from generic to pilot specific
		if(locationSimulation == "skive" or locationSimulation == "fur"):
			Pen = penDk
			nhouse = nhouseDk
			EconsumptionDk = avgP_house_pvDk * nhousePV + avgP_house_WithoutpvDk * houses_without_pv 
			Econsumption   = EconsumptionDk
		elif(locationSimulation == "bolzano"):
			Pen = penIt
			nhouse = nhouseIt
			EconsumptionIt = avgP_house_pvIt * nhousePV + avgP_house_WithoutpvIt * houses_without_pv 
			Econsumption   = EconsumptionDk
		else:
			print("[EconomicServer] S4G Unknown Location Provided "+str(locationSimulation))
			return str("[EconomicServer] S4G Unknown Location Provided "+str(locationSimulation))
		# ---------------------------------------------------------- #
		real_burocracy_cost = (burocracy * avg_res_EssCapacity) * resCounter + (burocracy * avg_dso_EssCapacity) * dsoCounter
		fixed_cost = real_burocracy_cost

		if(enableFullPrints == True):
			print("[EconomicServer] GS (Parameters): ")
			print("[EconomicServer] a0: " + str(a0))
			print("[EconomicServer] a1: " + str(a1))
			print("[EconomicServer] a2: " + str(a2))
			print("[EconomicServer] a3: " + str(a3))
			print("[EconomicServer] a4: " + str(a4))
			print("[EconomicServer] Steps Formula: ")
			print("[EconomicServer] [a4*((kwp)^4]=" + str(a4*((kwp)**4)))
			print("[EconomicServer] [a3*((kwp)^3)]=" + str(a3*((kwp)**3)))
			print("[EconomicServer] [a2*((kwp)^2)]=" + str(a2*((kwp)**2)))
			print("[EconomicServer] [a1*(kwp)]=" + str(a1*(kwp)))

		# ---------------------------------------------------------- #
		# Need to calculate the Grid Sthreghtening:
		gs  = a0 + a1*(kwp) + a2*((kwp)**2) + a3*((kwp)**3) + a4*((kwp)**4) 

		# Need to calculate the Grid Sthrenghtening Equivalent:
		gse = b0 + b1*(kwp) + b2*((kwp)**2)

		if(enableFullPrints == True):
			print("[EconomicServer] GS: " +str(gs))
			print("[EconomicServer] GSE: " +str(gse))

		# Directly related to the Grid Strenghtening values just built:
		CAPEX = gs
		OPEX  = 0.02*CAPEX

		# ---------------------------------------------------------- #
		# DEPRECATED
		# EconsumptionCost = Econsumption[ScenarioID] * Pen
		EconsumptionCost = Econsumption * Pen

		# TODO: Understand if the given Power Loss has to be converted!!!!
		# CPwLoss = Pen * pLoss
		CPwLoss = Pen * convertedPLoss

		if(enableFullPrints == True):
			print("[EconomicServer] CAPEX: " +str(CAPEX))
			print("[EconomicServer] OPEX: " +str(OPEX))
			print("[EconomicServer] Pen: " + str(Pen))
			print("[EconomicServer] PLoss: " + str(pLoss))
			print("[EconomicServer] EconsumptionCost: " +str(EconsumptionCost))
			print("[EconomicServer] CPwLoss: " +str(CPwLoss))
			print("[EconomicServer] simulationTime: " +str(simulationTime))

		# ---------------------------------------------------------- #
		# Common values for each Scenario built until now:
		# ---------------------------------------------------------- #
		# DEPRECATED
		# EconsumptionCostScenario0 = Econsumption[0] * Pen 

		# ---------------------------------------------------------- #
		# Now it is required to build up the Tables
		# Remember that some column are specific for each Scenario
		# ---------------------------------------------------------- #
		timeArray = [i for i in range(simulationTime+1)]
		if(ScenarioID == 0):
			if(enablePrints == True):
				print("[EconomicServer] Scenario 0 Evaluation")

			for x in timeArray:
				if(x == 0):
					# DSO_CF.append(CAPEX + CPwLoss)
					DSO_CF.append(CAPEX + CPwLoss * pSharedPLoss)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))
					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(CAPEX + CPwLoss))
						print("DSO_PV["+str(x)+"]="+str(DSO_CF[x]/((1+r)**(x))))

					if(DSO_CF[x] == 0): 
						PROSUMER_CF.append(0)
						PROSUMER_PV.append(0)
					else:
						# PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost * nhouse)
						# PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV))
						PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv)
						PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

				else:

					DSO_CF.append(OPEX + CPwLoss * pSharedPLoss)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(OPEX + CPwLoss * pSharedPLoss))
						print("DSO_PV["+str(x)+"]="+str(DSO_CF[x]/((1+r)**(x))))

					if(DSO_CF[x] == 0): 
						PROSUMER_CF.append(0)
						PROSUMER_PV.append(0)
					else:
						# PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost * nhouse)
						# PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV))
						PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv)
						PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

  
		elif(ScenarioID == 1):
			if(enablePrints == True):
				print("[EconomicServer] Scenario 1 Evaluation")
			# ---------------------------------------------------------- #
			# (ESS Capacity)  KWh_ess  = 12
			# (ESS LifeTime)  K - time = 15
			# ---------------------------------------------------------- #
			for x in timeArray:
				if(x == 0):
					DSO_CF.append(CAPEX + CPwLoss * pSharedPLoss)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					# tmpValue = (nss * residential_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + (nss * EconsumptionCost) + ( nhouse - nss ) * (EconsumptionCostScenario0)
					# tmpValue = (nss * residential_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV)				
					tmpValue = (nss * residential_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv				

					PROSUMER_CF.append(tmpValue)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

				else:
					DSO_CF.append(OPEX + CPwLoss)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					if((x % avg_res_EssLifetime) == 0):
						# TODO:
						# Here we need to repeat the estimation of the residential_capexSize 
						# by exploiting the estimated cost for that specific year:
						# Extract the estimation built about the current year:
						# elementRow = [z for z in simulatedBatteryData if z[0] == (year+x)]
						# Extract the proper value:
						# battSimulCost = elementRow[0][2]    
						# residential_capexSize = battSimulCost*avg_res_EssCapacity

						# tmpValue = (nss * residential_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + (nss * EconsumptionCost) + ( nhouse - nss ) * (EconsumptionCostScenario0)
						# tmpValue = (nss * residential_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV)
						tmpValue = (nss * residential_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv

					else:
						# tmpValue = CPwLoss * pSharedPLoss + nss * EconsumptionCost + (nhouse - nss) * EconsumptionCostScenario0
						# tmpValue = CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV)
						tmpValue = CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv

					PROSUMER_CF.append(tmpValue)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))
		# ---------------------------------------------------------- #
		elif(ScenarioID == 2):
			if(enablePrints == True):
				print("[EconomicServer] Scenario 2 Evaluation")
			
			for x in timeArray:
				if(x == 0):
					tmpValue = (nss * dso_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + (CAPEX + OPEX)
					
					DSO_CF.append(tmpValue)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					# PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCostScenario0 * nhouse)
					# PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV))
					PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

				else:
					if((x % avg_dso_EssLifetime) == 0):
						# TODO:
						# Here we need to repeat the estimation of the dso_capexSize 
						# by exploiting the estimated cost for that specific year:
						# Extract the estimation built about the current year:
						# elementRow = [z for z in simulatedBatteryData if z[0] == (year+x)]
						# Extract the proper value:
						# battSimulCost = elementRow[0][2]    
						# dso_capexSize = battSimulCost*avg_dso_EssCapacity
  
						tmpValue = (nss * dso_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + (CAPEX + OPEX)
					else:
						tmpValue = (pSharedPLoss * CPwLoss) + (OPEX)

					DSO_CF.append(tmpValue)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					# PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCostScenario0 * nhouse)
					# PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV))
					PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))
		# ---------------------------------------------------------- #
		elif(ScenarioID == 3):
			if(enablePrints == True):
				print("[EconomicServer] Scenario 3 Evaluation")

			for x in timeArray:
				if(x == 0):
					# ------------------------------------------------------------------------------------ #
					tmpValue = (dsoCounter * dso_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss*CPwLoss + (CAPEX + OPEX)
					# ------------------------------------------------------------------------------------ #
					DSO_CF.append(tmpValue)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					# ------------------------------------------------------------------------------------ #
					# tmpValue = (avg_res_EssLifetime * residential_capexSize * ( 1 + prudentAverageBatteries )**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost * resCounter + (nhouse - resCounter) * EconsumptionCostScenario0
					# tmpValue = (resCounter * residential_capexSize * ( 1 + prudentAverageBatteries )**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost * resCounter + (nhouse - resCounter) * EconsumptionCostScenario0
					# tmpValue = (resCounter * residential_capexSize * ( 1 + prudentAverageBatteries )**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV)
					tmpValue = (resCounter * residential_capexSize * ( 1 + prudentAverageBatteries )**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv
					# ------------------------------------------------------------------------------------ #
					PROSUMER_CF.append(tmpValue)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

					# ------------------------------------------------------------------------------------ #
				else:
					if((x % avg_dso_EssLifetime) == 0):
						# TODO:
						# Here we need to repeat the estimation of the dso_capexSize 
						# by exploiting the estimated cost for that specific year:
						# Extract the estimation built about the current year:
						# elementRow = [z for z in simulatedBatteryData if z[0] == (year+x)]
						# Extract the proper value:
						# battSimulCost = elementRow[0][2]    
						# dso_capexSize = battSimulCost*avg_dso_EssCapacity
						tmpValue = (dsoCounter * dso_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss*CPwLoss + (CAPEX + OPEX)
					else:
						tmpValue = (pSharedPLoss * CPwLoss) + (OPEX)
					# ------------------------------------------------------------------------------------ #
					DSO_CF.append(tmpValue)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))
					# ------------------------------------------------------------------------------------ #
					if((x % avg_res_EssLifetime) == 0):
						# TODO:
						# Here we need to repeat the estimation of the residential_capexSize 
						# by exploiting the estimated cost for that specific year:
						# Extract the estimation built about the current year:
						# elementRow = [z for z in simulatedBatteryData if z[0] == (year+x)]
						# Extract the proper value:
						# battSimulCost = elementRow[0][2]    
						# residential_capexSize = battSimulCost*avg_res_EssCapacity

						# tmpValue = (avg_res_EssLifetime * residential_capexSize * (1 + prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost * resCounter + (nhouse - resCounter) * EconsumptionCostScenario0
						# tmpValue = (resCounter * residential_capexSize * (1 + prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost * resCounter + (nhouse - resCounter) * EconsumptionCostScenario0
						# tmpValue = (resCounter * residential_capexSize * (1 + prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV)
						tmpValue = (resCounter * residential_capexSize * (1 + prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv

					else:
						# tmpValue = CPwLoss * pSharedPLoss + EconsumptionCost * resCounter + (nhouse - resCounter) * EconsumptionCostScenario0
						# tmpValue = CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * (nhouse - nhousePV)
						tmpValue = CPwLoss * pSharedPLoss + EconsumptionCost_PV * nhousePV + EconsumptionCost_without_PV * houses_without_pv
					# ------------------------------------------------------------------------------------ #
					PROSUMER_CF.append(tmpValue)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer] S4G Service [Starting Economic Evaluation] Error %s" %e)
		return str("[EconomicServer] S4G Service [Starting Economic Evaluation] Error %s" %e)

	# -------------------- #
	# Final Results:
	# -------------------- #
	TCO_DSO        = sum(DSO_PV)
	TCO_PROSUMER   = sum(PROSUMER_PV)	
	TCO_COMMUNITY  = TCO_DSO + TCO_PROSUMER
	# TCO_DIFFERENCE = TCO_COMMUNITY - TCO_DSO # DEPRECATED
	# -------------------- #
	if(enablePrints == True):
		print("[EconomicServer] Identified Scenario: [" + str(ScenarioID) + "]")
		print("[EconomicServer] Identified Scenario: [" + str(scenarioDescription[ScenarioID]) + "]")
		print("[EconomicServer] TCO(DSO): "        + str(int(TCO_DSO)))
		print("[EconomicServer] TCO(HOUSEHOLDS): "   + str(int(TCO_PROSUMER)))
		# print("[EconomicServer] TCO(DIFFERENCE): " + str(int(TCO_DIFFERENCE)))
		print("[EconomicServer] TCO(COMMUNITY): "  + str(int(TCO_COMMUNITY)))
		# To build the incentive we should store the simulation results... deprecated!
		# print("[EconomicServer] Incentive: "  + str())

	# -------------------- #
	# Must Return a JSON:
	#{
	#"simulation_id":0,
	#"scenario_id":1,
	#"scenario_name":"AA",
	#"TCO_DSO":10,
	#"TCO_Difference":110,
	#"TCO_Community":90
	#}
	# -------------------- #
	#result = {"simulation_id":idSimulation,"scenario_id":ScenarioID,"scenario_name":str(scenarioDescription[ScenarioID]),\
	#	 "TCO_DSO":TCO_DSO,"TCO_Difference":TCO_DIFFERENCE,"TCO_Community":TCO_COMMUNITY}
	# -------------------- #
	# Before 2020-02-03
	# result = {"simulation_id":idSimulation,"scenario_id":ScenarioID,"scenario_name":str(scenarioDescription[ScenarioID]),\
	#	 "TCO_DSO":TCO_DSO,"TCO_Households":TCO_PROSUMER,"TCO_Community":TCO_COMMUNITY}
	# -------------------- #
	result = {"simulation_id":idSimulation,"scenario_id":ScenarioID,"scenario_name":str(scenarioDescription[ScenarioID]),\
		 "Economic_Model_Simulation_Time":simulationTime,\
		 "TCO_DSO":int(TCO_DSO),"TCO_DSO_YEARLY":int(TCO_DSO/simulationTime),\
		 "TCO_Households":int(TCO_PROSUMER),"TCO_Households_YEARLY":int(TCO_PROSUMER/simulationTime),\
		 "TCO_Community":int(TCO_COMMUNITY),"TCO_Community_YEARLY":int(TCO_COMMUNITY/simulationTime)}

	# -------------------- #
	return json.dumps(result)

# ------------------------------------------------------------------------------------ #
# IF the current python application is triggered by uWSGI it means that 
# the following main() will never be executed!
# ------------------------------------------------------------------------------------ #
if __name__ == "__main__":
	print((sys.version_info))
	print("Storage4Grid EU Project: Implementation of EconomicServer Backend")
	print("[EconomicServer-Backend] Restoring back the Server configuration")
	print("[EconomicServer-Backend] Starting REST Server")
	if(localDebugHTTP == True):
		print("[EconomicServer-Backend] DEBUGGING MODE! ONLY FOR LOCAL PURPOSES!")
		app.run(host='0.0.0.0', port=9082) # HTTP
	else:
		print("[EconomicServer-Backend] PRODUCTION MODE!") # HTTPS
		# app.run(ssl_context=('ssl/nginx-selfsigned.crt', 'ssl/nginx-selfsigned.key'), port=9082)
		app.run(ssl_context=('/etc/letsencrypt/live/dwh.storage4grid.eu/fullchain.pem', '/etc/letsencrypt/live/dwh.storage4grid.eu/privkey.pem'), port=9082)
