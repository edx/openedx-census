# Makefile for openedx-census

.PHONY: help dev install

help: 				## display this help message
	@echo "Please use \`make <target>' where <target> is one of:"
	@grep '^[a-zA-Z]' $(MAKEFILE_LIST) | sort | awk -F ':.*?## ' 'NF==2 {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}'

dev: install			## prepare for development
	pip install -r dev-requirements.txt

install:			## install this project to run it
	pip install -e .
	mkdir -p refs state html

clean:				## remove all transient files
	rm refs/*.* state/*.* html/*.* course-ids.txt update.json
	rm -rf save

## Data management

# Where Ned kept it
OPENEDX_STATS_DIR = /src/edx/src/openedxstats

.PHONY: save_referer_history fetch_referrer_logs get_referers get_known

save_referer_history:		## save current referers in the history directory
	mv -n refs/referers.txt "refs/history/referers_$$(date -r refs/referers.txt +"%Y%m%d").txt"

fetch_referer_logs:		## use openedxstats to get the latest referer logs
	cd $(OPENEDX_STATS_DIR) && heroku run python manage.py fetch_referrer_logs

get_referers:			## get the latest referrers and aliases
	./get-domains.sh

get_known:			## pull down the csv of known sites
	census getcsv

## Scraping

.PHONY: new_sites all_sites known_sites post

new_refs:			## scrape new referrers in the last 2 months
	@# Sorry for the shell craziness!
	@# date -v-2m    gives us the date of two months ago, so we can see the new referrers.
	comm -13 refs/history/$$(ls -1 refs/history | awk '{if ($$0 < "referers_'$$(date -v-2m '+%Y%m%d')'.txt") print}' | tail -1) refs/referers.txt > refs/new-refs.txt
	census refscrape --out state/new-refs.pickle refs/new-refs.txt
	census html --in state/new-refs.pickle --out html/new-refs.html --skip-none --only-new

all_refs:			## scrape all referrers ever
	census refscrape --out state/all-refs.pickle refs/referers.txt
	census html --in state/all-refs.pickle --out html/all-refs.html --skip-none --only-new

known_sites:			## scrape the known sites
	census scrape --gone && census summary && census html && census json

post:				## update the stats site with the latest known_sites scrape
	census post
