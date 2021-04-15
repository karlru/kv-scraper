import kv_scraper

params1 = {
	# 1=sell, 2=rent, 30=short time rent, 20=all
	'deal_type': 2,
	# 1=harjumaa, 12=tartumaa
	'county': 12,
	# 1061=tallinn, 1063=tartu
	'parish': 1063,
	# 5704=karlova, 5705=kesklinn, 5716=supilinn, 5714=tähtvere, 5710=ülejõe, 5711=vaksali
	'city': [5704, 5705, 5716, 5714, 5710, 5711],
	'rooms_min': 3,
	'rooms_max': 4,
	'price_min': 0,
	'price_max': 400,
}

params2 = {
	'deal_type': 2,
	'county': 12,
	'parish': 1063,
	'price_min': 350,
	'price_max': 350,
}

params3 = {
	'deal_type': 2,
	'county': 12,
}