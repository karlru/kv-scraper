from requests import get as http_get
import json
from sys import exit
from bs4 import BeautifulSoup
import re
from pprint import pprint

class Search:
	# args:
	#	params (dict/list of dicts)

	# returns:
	#	listings ()

	allowed_params = [
		'deal_type',
		'county',
		'parish',
		'city',
		'rooms_min',
		'rooms_max',
		'price_min',
		'price_max',
	]

	def __init__(self, params):
		if type(params) == dict:
			query = SearchQuery(params)

class SearchQuery:
	# args:
	#	args (dict)
	#		deal_type (int/str) 1-sell, 2-rent, 30-short time rent, 20-all
	#		county (int/str) possible to get options from getKvAreas
	#		parish (int/str) possible to get options from getKvAreas
	#		city (list of int/str) possible to get options from getKvAreas
	#		rooms_min (int/str)
	#		rooms_max (int/str)
	#		price_min (int/str)
	#		price_max (int/str)

	# returns:
	#	listings (dict)
	#		request_url (str)
	#		urls (dict)
	#			obj_id (int) => obj_link (str)
	#		count (int)

	def __init__(self, args):
		self.base_url = 'https://www.kv.ee/?act=search.simple&search_type=new&page_size=50'

		self.args = args

		self.listings = {}

		self.listings['request_url'] = self.getRequestUrl()
		self.listings['urls'] = self.getListingsUrls()
		self.listings['count'] = len(self.listings['urls'].keys())

	def getRequestUrl(self):
		request_url = self.base_url

		for key, val in self.args.items():
			if type(val) in [int, str]:
				request_url += f'&{key}={val}'
			# convert list of city ids to acceptable query params
			if type(val) == list:
				for n, city in enumerate(val):
					request_url += f'&{key}%5B{n}%5D={city}'

		return request_url

	def getListingsUrls(self):
		listings = {}

		request = http_get(self.listings['request_url'])
		
		if not request.ok:
			exit('request error') 

		soup = BeautifulSoup(request.text, 'html.parser')

		listings.update(self.getListingsUrlsFromSoup(soup))

		page_count = soup.find('a', 'count')
		if page_count:
			page_count = int(page_count.text.strip())

			for page in range(2, page_count + 1):
				request = http_get(f'{self.listings["request_url"]}&page={page}')
				soup = BeautifulSoup(request.text, 'html.parser')
				listings.update(self.getListingsUrlsFromSoup(soup))

		return listings

	def getListingsUrlsFromSoup(self, soup):
		listings = {}
		for el in soup.find_all('tr', 'object-item'):
			el_id = el.get('id')
			listings[int(el_id)] = f'https://www.kv.ee/{el_id}'

		return listings

class Listing:
	# args:
	#	listing (dict)
	#		obj_id (int) => obj_link (str)

	# returns (only if said value is set):
	#	listing (dict)
	#		obj_id (int)
	#			obj_info (dict)
	#				price (int)
	#				rooms (int)
	#				area (float)
	#				condition (int, on a scale of 1-7)
	#				year_built (int)
	#				story (int)
	#				energy_label (str)
	#				cost_summer (int)
	#				cost_winter (int)
	#				cadastre_nr (str)

	condition = {
		'Vajab renoveerimist': 1,
		'Vajab san. remonti': 2,
		'Keskmine': 3,
		'San. remont tehtud': 4,
		'Renoveeritud': 5,
		'Heas korras': 6,
		'Uus': 7,
		'Uusarendus': 8,
	}

	switcher = {
		'tube': 
			(lambda val : {
				'rooms': int(val)
			}),
		'üldpind': 
			(lambda val : {
				'area': float(re.search(r'\d+(?:\.(?:\d))?', val).group())
			}),
		'ehitusaasta': 
			(lambda val : {
				'year_built': int(val)
			}),
		'seisukord': 
			(lambda val : {
				'condition': condition[val]
			} if val in condition else {}),
		'korrus/korruseid': 
			(lambda val : {
				'story': int(re.search(r'(\d+)(?:\/\d+)', val).group(1))
			}),
		'energiamärgis': 
			(lambda val : (lambda l : {
				'energy_label': l.group()
			} if l and l.group() != 'P' else {})(re.search(r'[A-Z]{1}', val))),
		'kulud suvel/talvel': 
			(lambda val : (lambda costs : {
				'cost_summer': int(costs[0]), 
				'cost_winter': int(costs[1])
			} if len(costs) == 2 else {})(re.findall(r'(\d+)', val))),
		'katastrinumber':
			(lambda val : {
				'cadastre_nr': str(val)
			}),
	}

	def __init__(self, listing):
		pass

	def getListingsData(self):
		# warning: kv listing data html isn't in the cleanest
		# so extracting data is quite messy

		listings_data = {}

		for obj_id, link in self.listings['urls'].items():
			listings_data[obj_id] = {}

			request = http_get(link)
			soup = BeautifulSoup(request.text, 'html.parser')

			price_info = soup.find('div', 'object-price')
			price = price_info.findChild('strong').text.strip()
			price = re.search(r'(\d+)', price)
			if price:
				listings_data[obj_id].update({'price': int(price.group())})
			
			main_info_grid = soup.find_all('table', 'object-data-meta')[-1]
			for row in main_info_grid.findChildren('tr'):
				key = row.findChild('th')
				val = row.findChild('td')
				if key and val:
					key = key.text.lower().strip()

					if key in switcher:
						new = switcher[key](val.text.strip())
						listings_data[obj_id].update(new)

			extra_info_grid = ''

		return listings_data

class Area():
	# area_type (str) county/parish/city
	# parent_area_id (int)
	def getKvAreas(self, area_type, parent_area_id=False):
		area_types = {
			'county': 'counties', 
			'parish': 'parishes', 
			'city': 'cities',
		}
		
		if area_type not in list(area_types.keys()):
			exit('invalid param area_type')

		if parent_area_id:
			parent_area_list_index = list(area_types.keys()).index(area_type) - 1
			parent_area_type = list(area_types.keys())[parent_area_list_index]


		url = f'http://api.kv.ee/api/{area_types[area_type]}'
		params = {
			'pagination': False,

		}

		if parent_area_id:
			params[f'{parent_area_type}_id'] = parent_area_id

		response = http_get(url, params=params)
		
		return response.json()
