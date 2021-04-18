from requests import get as http_get
import json
from sys import exit
from bs4 import BeautifulSoup
import re

class Search:
	def __init__(self, params):
		self.success = True
		self.data = {}
		self.error = ''

		if type(params) not in [dict, list]:
			self.success = False
			self.error = 'param object not type dict or list'
			return

		if type(params) == dict:
			params = [params]

		if not all(type(param) == dict for param in params):
			self.success = False
			self.error = 'param object not type dict'
			return

		for index, params_dict in enumerate(params):
			self.data[index] = {}

			query = SearchQuery(params_dict)

			self.data[index].update({'query': query})
			self.data[index].update({'listings': []})

			self.setStatus(f'getting listings {index+1}/{len(params)}')
			query_listings = query.getListingsUrls()

			for obj_id, obj_url in query_listings.items():
				listing = Listing(obj_id, obj_url)
				self.setStatus(f'analyzing listings {list(query_listings.keys()).index(obj_id)+1}/{len(query_listings)}')
				listing.data = listing.getListingData()

				self.data[index]['listings'].append(listing)

		self.setStatus('finishing up')

	def setStatus(self, status):
		print(status)

class SearchQuery:
	base_url = 'https://www.kv.ee/?act=search.simple&search_type=new&page_size=100'
	
	allowed_args = [
		'deal_type',
		'county',
		'parish',
		'city',
		'rooms_min',
		'rooms_max',
		'price_min',
		'price_max',
	]

	def __init__(self, args):
		self.args = args

		self.request_url = self.getRequestUrl()

	def cleanArgs(self):
		return {k:v for (k, v) in self.args.items() if k in self.allowed_args}

	def getRequestUrl(self):
		request_url = self.base_url

		for key, val in self.cleanArgs().items():
			if type(val) in [int, str]:
				request_url += f'&{key}={val}'
			# convert list of city ids to acceptable query params
			if type(val) == list:
				for n, city in enumerate(val):
					request_url += f'&{key}%5B{n}%5D={city}'

		return request_url

	def getListingsUrls(self):
		listings = {}

		request = http_get(self.request_url)
		
		if not request.ok:
			exit('request error') 

		soup = BeautifulSoup(request.text, 'html.parser')

		listings.update(self.getListingsUrlsFromSoup(soup))

		page_count = soup.find('a', 'count')
		if page_count:
			page_count = int(page_count.text.strip())

			for page in range(2, page_count + 1):
				request = http_get('{}&page={}'.format(self.request_url, page))
				soup = BeautifulSoup(request.text, 'html.parser')
				listings.update(self.getListingsUrlsFromSoup(soup))

		return listings

	def getListingsUrlsFromSoup(self, soup):
		listings = {}
		for el in soup.find_all('tr', 'object-item'):
			el_id = el.get('id')
			listings[int(el_id)] = f'https://www.kv.ee/{el_id}'

		return listings

	def __repr__(self):
		return str({
			'args': self.args,
			'request_url': self.request_url,
		})

class Listing:
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
				'condition': Listing.condition[val]
			} if val in Listing.condition else {}),
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
	}

	def __init__(self, obj_id, link):
		self.id = obj_id
		self.link = link
		self.data = {}

	def getListingData(self):
		# warning: kv listing data html isn't in the cleanest
		# so extracting data is quite messy
		data = {}

		request = http_get(self.link)
		soup = BeautifulSoup(request.text, 'html.parser')
		
		price_info = soup.find('div', 'object-price')
		price = price_info.findChild('strong').text.strip()
		price = re.search(r'(\d+)', price)
		if price:
			data.update({'price': int(price.group())})
		
		main_info_grid = soup.find_all('table', 'object-data-meta')[-1]
		for row in main_info_grid.findChildren('tr'):
			key = row.findChild('th')
			val = row.findChild('td')
			if key and val:
				key = key.text.lower().strip()
				if key in self.switcher:
					new = self.switcher[key](val.text.strip())
					data.update(new)

		coordinates = soup.find('a', 'icon icon-new-tab gtm-object-map')['href']
		coordinates = re.findall(r'(\d{2}.\d{7})', coordinates)
		data.update({'coordinates': coordinates})

		return data

		def __repr__(self):
			return str(self.data.price)

class Area:
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
