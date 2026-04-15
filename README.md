# HZZ Job Scrapper

## Description
Scraps jobs in Brodsko-posavska county listed on the Croatian employment office website and creates a web page (`output/index.html`) with a table overview of that allows quick filtering.

## Legal Notice
Distributing data from Croatian employment office website to third-parties is prohibited without written consent. Read their [Terms and Services](https://www.hzz.hr/uvjeti-koristenja/) for more info.

## Prerequisites
1. Python 3.12. or newer
2. `requests` Python module

## Installation
`git clone https://github.com/zenon-mesic/hzz_job_scrapper`

## Usage
`python3 main.py`

## Project Structure
Folder `static` contains:
1. `datatables.css` / `datatables.js` downloaded from https://datatables.net/, offering table filtering function.
2. `script.js` that servers as a configuration file. for DataTables
3. `syles.css` with some basic styling.

Folder `templates` contains `templates.html` which servers as a template for the script's output HTML file.

`database.py` handles SQLite3 operations.

`jobs.py` handles job scrapping and prepares data for SQLite3.

## API Reference
Active jobs' IDs are first gathered from HZZ's [RSS feed](https://burzarada.hzz.hr/rss/rsszup2.xml). Individual job infos are then scrapped from a job's respective web page.