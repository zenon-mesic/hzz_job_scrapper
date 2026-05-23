import asyncio
import logging
import os
import re
import time
from datetime import datetime as dt
from typing import Any

from database import Database
from job import Job


def return_pct_string(subset: int, total: int) -> str:
    """
    Returns a string showing how much of total the subtotal represents.

    Example:
    subset = 5, total = 20 --> '25 %'
    """
    subset_procent = (subset * 100) // total
    return f"{str(subset_procent)} %"


def insert_stats_and_date_into_html(db_stats: dict[str, int], html: str) -> str:
    """
    Inserts stats fetched from a database and today's date into an HTML template.
    """
    page_info_datetime = dt.today().strftime("%Y-%m-%d")
    page_info_last_updated = dt.today().strftime("%d.%m.%Y")
    total_jobs = str(db_stats["total_jobs"])
    jobs_in_sb = str(db_stats["jobs_in_sb"])
    jobs_in_sb_pct = return_pct_string(db_stats["jobs_in_sb"], db_stats["total_jobs"])
    unlimited_jobs = str(db_stats["unlimited_jobs"])
    unlimited_jobs_pct = return_pct_string(
        db_stats["unlimited_jobs"], db_stats["total_jobs"]
    )
    unlimited_possible_jobs = str(db_stats["unlimited_possible_jobs"])
    unlimited_possible_jobs_pct = return_pct_string(
        db_stats["unlimited_possible_jobs"], db_stats["total_jobs"]
    )
    full_time_jobs = str(db_stats["full_time_jobs"])
    full_time_jobs_pct = return_pct_string(
        db_stats["full_time_jobs"], db_stats["total_jobs"]
    )
    drivers_license_jobs = str(db_stats["drivers_license_jobs"])
    drivers_license_jobs_pct = return_pct_string(
        db_stats["drivers_license_jobs"], db_stats["total_jobs"]
    )

    html = html.replace("{{ page_info_datetime }}", page_info_datetime)
    html = html.replace("{{ page_info_last_updated }}", page_info_last_updated)
    html = html.replace("{{ total_jobs }}", total_jobs)
    html = html.replace("{{ jobs_in_sb }}", jobs_in_sb)
    html = html.replace("{{ jobs_in_sb_pct }}", jobs_in_sb_pct)
    html = html.replace("{{ unlimited_jobs }}", unlimited_jobs)
    html = html.replace("{{ unlimited_jobs_pct }}", unlimited_jobs_pct)
    html = html.replace("{{ unlimited_possible_jobs }}", unlimited_possible_jobs)
    html = html.replace(
        "{{ unlimited_possible_jobs_pct }}", unlimited_possible_jobs_pct
    )
    html = html.replace("{{ full_time_jobs }}", full_time_jobs)
    html = html.replace("{{ full_time_jobs_pct }}", full_time_jobs_pct)
    html = html.replace("{{ drivers_license_jobs }}", drivers_license_jobs)
    html = html.replace("{{ drivers_license_jobs_pct }}", drivers_license_jobs_pct)
    return html


def format_unlimited(row: dict[str, str | int]) -> str:
    """
    Combines input from unlimited and unlimited_possible database rows.

    unlimited and unlimited_possible can be either 0 or 1. Those two database
    columns are combined into a single HTML table column with values 'Yes',
    'No' or 'Possible'.
    """
    if row["unlimited"] == 1:
        unlimited = "Yes"
    elif row["unlimited_possible"] == 1:
        unlimited = "Possible"
    else:
        unlimited = "No"
    return unlimited


def db_row_to_html_row(row: dict[str, Any], html_row_template: str) -> str:
    """Converts a dictionary returned by the database into an HTML table row."""
    unlimited = format_unlimited(row)
    link = (
        '<a href="https://burzarada.hzz.hr/RadnoMjesto_Ispis.aspx?WebSifra='
        f'{row["id"]}">Link</a>'
    )
    full_time = "Yes" if row["full_time"] else "No"
    drivers_license = "Yes" if row["drivers_license"] else "No"
    html_row = html_row_template
    html_row = html_row.replace("{{ title }}", row["title"])
    html_row = html_row.replace("{{ location }}", row["location"])
    html_row = html_row.replace("{{ unlimited }}", unlimited)
    html_row = html_row.replace("{{ full_time }}", full_time)
    html_row = html_row.replace("{{ drivers_license }}", drivers_license)
    html_row = html_row.replace("{{ date_added }}", row["date_added"])
    html_row = html_row.replace("{{ date_apply_end }}", row["date_apply_end"])
    html_row = html_row.replace("{{ employer }}", row["employer"])
    html_row = html_row.replace("{{ link }}", link)
    return html_row


def insert_db_rows_into_html(rows: list[dict[str, Any]], html: str) -> str:
    """Inserts a database row into the HTML template."""
    tbody_start_index = html.find("<tbody>")
    row_start_search = re.search(r"\s+<tr>", html[tbody_start_index:])
    if row_start_search is None:
        return ""

    row_start = row_start_search.group()
    row_start_index = html.find(row_start, tbody_start_index)
    row_end_search = re.search(r"\s+</tr>", html[row_start_index:])
    if row_end_search is None:
        return ""

    row_end = row_end_search.group()
    row_end_index = html.find(row_end, row_start_index) + len(row_end)
    html_start = html[:row_start_index]
    html_end = html[row_end_index:]
    html_row_template = html[row_start_index:row_end_index]
    html_rows = ""
    for row in rows:
        html_row = db_row_to_html_row(row, html_row_template)
        html_rows += html_row + "\n"
    html = html_start + html_rows[:-1] + html_end
    return html


async def update_database(
    db_filepath: str, xml_jobs: list[Job]
) -> tuple[list[dict], dict]:
    """
    Takes a list of Job objects and performs all required database operations.

    Those operations are:
    - delete jobs from the database whose application end explired
    - delete jobs from the database that were manually removed from the website
    - remove Job objects from the list already present in the database
    - fetches each job's data with an HTTP request
    - inserts new jobs into database
    - selects all jobs from the database to for further processing
    - selects predefined database stats for further processing
    """
    with Database(db_filepath) as db:
        db.delete_expired_jobs()
        db.delete_removed_jobs(xml_jobs)
        xml_jobs = db.pop_existing_jobs(xml_jobs)
        async_tasks = []
        for job in xml_jobs:
            task = asyncio.to_thread(job.fetch_details)
            async_tasks.append(task)
        try:
            await asyncio.gather(*async_tasks)
        except Exception as error:
            logging.exception(error)
        db.insert_new_jobs(xml_jobs)
        db_jobs: list[dict[str, Any]] = db.select_all_jobs()
        db_stats: dict[str, int] = db.get_statistics()
        logging.info("All database operations completed")
        return db_jobs, db_stats


def create_html(
    template_filepath: str,
    output_filepath: str,
    db_jobs: list[dict[str, Any]],
    db_stats: dict[str, int],
) -> None:
    """Takes database information and inserts it into an HTML template"""
    with open(template_filepath, "r") as f:
        html = f.read()
    html = insert_stats_and_date_into_html(db_stats, html)
    html = insert_db_rows_into_html(db_jobs, html)
    if html == "":
        logging.warning("Failed to insert DB rows into HTML. Row element not found")
        return
    output_dir = os.path.dirname(output_filepath)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    with open(output_filepath, "w") as f:
        f.write(html)
    logging.info("index.html created")
    logging.info("Daily update completed")


def start_logging(log_filepath: str) -> None:
    logging.basicConfig(
        filename=log_filepath,
        level=logging.INFO,
        format="{asctime} [{levelname}] [{filename}:{lineno}] {message}",
        style="{",
    )


def create_log(log_filepath: str) -> bool:
    dir, file = os.path.split(log_filepath)
    if file == "":
        return False
    if dir != "" and not os.path.exists(dir):
        os.mkdir(dir)
    open(log_filepath, "a")
    return True


async def main() -> None:
    """
    Initialises logging, fetches job listing XML, updates DB and creates HTML.
    """
    start_time = time.perf_counter()
    log_filepath = "logs/app.log"
    create_log(log_filepath)
    start_logging(log_filepath)
    logging.info("Daily update started")
    hzz_job_xml: str = Job.fetch_job_xml()
    if hzz_job_xml == "":
        return  # fetch failed
    xml_jobs: list[Job] = Job.extract_jobs(hzz_job_xml)
    db_jobs, db_stats = await update_database("jobs.db", xml_jobs)
    create_html("templates/template.html", "output/index.html", db_jobs, db_stats)
    end_time = time.perf_counter()
    logging.info(f"Ran for {end_time - start_time} seconds")


if __name__ == "__main__":
    asyncio.run(main())
