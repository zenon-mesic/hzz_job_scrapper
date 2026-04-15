from __future__ import annotations # otherwise -> list[Job] raises NameError
from dataclasses import dataclass
import requests
import xml.etree.cElementTree as ET
import logging
import datetime as dt

logger = logging.getLogger(__name__)

@dataclass
class Job():
  """
  A class that represents a job scrapped from the HZZ website.

  The class contains methods that:
  - make an HTTP request to the HZZ website to fetch a list of all active jobs
    and individual HTTP requests to each job's website to fetch its details
  - extracts job list from the fetched XML file
  - extracts job details from the fetched HTML files
  - format dates
  - converts Job object into a ready-to-use tuple for SQLite
  
  The class also contains a lot of helper methods that power the functions
  listed above.

  Only id and date_added properties are in the constructor. The rest of
  the properties are initialized to None, signaling an invalid / uninitalized
  value. If job data is fetched properly later on, all properties should either
  be an int or a string.
  """
  id: int
  date_added: str
  title: str | None = None
  location: str | None = None
  unlimited: int | None = None
  unlimited_possible: int | None = None
  full_time: int | None = None
  drivers_license: int | None = None
  date_apply_start: str | None = None
  date_apply_end: str | None = None
  employer: str | None = None

  @staticmethod
  def fetch_job_xml() -> str:
    """Fetches the XML file containing a list of all active jobs."""
    hzz_api_url = 'https://burzarada.hzz.hr/rss/rsszup2.xml'
    try:
      req = requests.get(hzz_api_url, timeout=(3, 10))
      req.raise_for_status()
    except Exception:
      logger.exception('Failed to fetch jobs')
      return ''
    else:
      return req.text
  
  @staticmethod
  def format_hzz_date(date: str) -> str:
    """Formats HZZ dates: 01.3.2025. --> 2025-03-01"""
    date_split = date.split('.')
    for i in range(2):
      if len(date_split[i]) == 1:
        date_split[i] = f'0{date_split[i]}'
    return f'{date_split[2]}-{date_split[1]}-{date_split[0]}'

  @staticmethod
  def is_valid_xml_el(xml_el: ET.Element | None) -> bool:
    """Checks if an XML element found by ET module is valid / not empty."""
    if xml_el is None or xml_el.text is None or xml_el.text == '':
      return False
    
    return True

  @staticmethod
  def extract_jobs(hzz_jobs_xml: str) -> list[Job]:
    """Converts XML data to Job(id, published_date) objects."""
    root = ET.fromstring(hzz_jobs_xml)
    jobs: list[Job] = []

    for item in root.findall('./channel/item'):
      guid_el = item.find('guid')

      if not Job.is_valid_xml_el(guid_el):
        logger.warning(
          'Failed to extract job. '
          f'Failed to extract guid: {item.text=}'
        )
        continue
      try:
        guid = int(guid_el.text.split('=')[-1]) # type: ignore
      except Exception:
        logger.exception(
          'Failted to extract job. '
          f'Failed to convert guid to int: {guid_el.text=}' # type: ignore
        )
        continue

      publish_date = dt.date.today().strftime('%Y-%m-%d')
      jobs.append(Job(guid, publish_date))

    return jobs

  @staticmethod
  def extract_substring(text: str, prefix: str, suffix: str) -> str:
    """Extracts a substring starting with prefix and ending wtih suffix."""
    start = text.find(prefix)
    if start == -1:
      return ''
    start += len(prefix)
    
    end = text.find(suffix, start)
    if end == -1:
      return ''
    
    return text[start:end].strip()
  
  def has_all_data(self) -> bool:
    """
    Checks if a Job object is valid.

    A Job object is considered valid if all of its properties are not None.
    That implies that the HTTP request and the extraction of HTML data were
    successful.
    """
    return not any(value is None for value in vars(self).values())

  def fetch_html_data(self) -> str:
    """Fetches the HTML from the job's individual website."""
    job_url = (
      'http://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra='
      f'{self.id}'
    )
    try:
      req = requests.get(job_url, timeout=(3, 10))
      req.raise_for_status()
    except Exception:
      return ''
    else:
      return req.text

  def fetch_details(self) -> None:
    """
    Fetches the HTML from job's web page and extracts job's details from it.
    """
    job_html = self.fetch_html_data()
    if job_html == '':
      raise Exception('Failed to fetch job HTML (GET failed)')
    if 'Traženi oglas je istekao!' in job_html:
      return
    self.title = self.extract_title(job_html)
    self.location = self.extract_location(job_html)
    self.unlimited = self.extract_unlimited(job_html)
    self.unlimited_possible = self.extract_unlimited_possible(job_html)
    self.full_time = self.extract_full_time(job_html)
    self.drivers_license = self.extract_drivers_license(job_html)
    self.date_apply_start = self.extract_date_apply_start(job_html)
    self.date_apply_end = self.extract_date_apply_end(job_html)
    self.employer = self.extract_employer(job_html)
  
  def extract_title(self, job_html: str) -> str:
    """Extracts job's title from the fetched HTML."""
    title_prefix = '<h3>'
    title_suffix = '</h3>'
    title = Job.extract_substring(job_html, title_prefix, title_suffix)
    return title.capitalize()
  
  def extract_location(self, job_html: str) -> str:
    """Extracts job's location from the fetched HTML."""
    location_prefix = '<span id="ctl00_MainContent_lblMjestoRada">'
    location_suffix = '</span>'
    location = Job.extract_substring(
      job_html,
      location_prefix,
      location_suffix
      )
    location_split = location.split(',')
    return location_split[0].title()
  
  def extract_unlimited(self, job_html: str) -> int:
    """Returns 1 if an unlimited contract is offered, otherwise 0."""
    return int('Na neodređeno;' in job_html)
  
  def extract_unlimited_possible(self, job_html: str) -> int:
    """Returns 1 if an unlimited contract is possible, otherwise 0."""
    return int('Mogućnost stalnog zaposlenja.' in job_html)

  def extract_full_time(self, job_html: str) -> int:
    """Returns 1 if the job is full-time, otherwise 0."""
    return int('Puno radno vrijeme' in job_html)
  
  def extract_drivers_license(self, job_html: str) -> int:
    """Returns 1 if a driver's license is required, otherwise 0."""
    return int('Vozački ispit:' in job_html)

  def extract_date_apply_start(self, job_html: str) -> str:
    """Extracts job application start date from the fetched HTML."""
    date_apply_start_prefix = '<span id="ctl00_MainContent_lblVrijediOd">'
    date_apply_start_suffix = '</span>'
    date_apply_start = Job.extract_substring(
      job_html,
      date_apply_start_prefix,
      date_apply_start_suffix
      )
    return Job.format_hzz_date(date_apply_start)

  def extract_date_apply_end(self, job_html: str) -> str:
    """Extracts job application end date from the fetched HTML."""
    date_apply_end_prefix = '<span id="ctl00_MainContent_lblVrijediDo">'
    date_apply_end_suffix = '</span>'
    date_apply_end = Job.extract_substring(
      job_html,
      date_apply_end_prefix,
      date_apply_end_suffix
      )
    return Job.format_hzz_date(date_apply_end)
  
  def extract_employer(self, job_html: str) -> str:
    """Extracts employer information the fetched HTML."""
    employer_prefix = '<span id="ctl00_MainContent_lblNazivPoslodavca">'
    employer_suffix = '</span>'
    employer = Job.extract_substring(
      job_html,
      employer_prefix,
      employer_suffix
      )
    return employer

  def export_sql_values(self) -> tuple:
    """Converts Job object's properties into a tuple for SQLite."""
    if not self.has_all_data():
      raise Exception(
        f'\nExport SQL values aborted.\nData missing for {self.id}.\n'
        )
    return (
      self.id,
      self.title,
      self.location,
      self.unlimited,
      self.unlimited_possible,
      self.full_time,
      self.drivers_license,
      self.date_added,
      self.date_apply_start,
      self.date_apply_end,
      self.employer
    )