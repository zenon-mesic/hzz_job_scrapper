import sqlite3
from job import Job
import datetime
import logging

logger = logging.getLogger(__name__)

class Database():
  """
  A class that enables working with an SQLite database.

  The class only offers those database operations that are relevant to the
  project.
  The class uses row_factory=sqlite3.Row so that
  sqlite3.cursor.fetchall() returns sqlite3.Row objects instead of tuples.
  sqlite3.Row provides indexed and case-insensitive named access to columns,
  with minimal memory overhead and performance impact over a tuple. It's much
  easier to work with row dictionaries than with row tuples in external code.
  Adding or deleting columns in tables won't break (external) code using
  dictionaries (as long as column names stay the same), but will break code
  using tuples because indexes will change. sqlite3.Row can be easily converted
  to a dictionary with dict(sqlite3.Row)
  """
  def __init__(self, db: str) -> None:
    self._conn = sqlite3.connect(db)
    self._conn.row_factory = sqlite3.Row
    self._cur = self._conn.cursor()
    create_table_query = Database.get_create_table_query()
    self._cur.execute(create_table_query)
    self._conn.commit()

  def __enter__(self):
    return self
  
  def __exit__(self, exc_type, exc, tb):
    self._conn.close()
  
  @staticmethod
  def get_create_table_query():
    return """
      CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        location TEXT NOT NULL,
        unlimited INTEGER NOT NULL
          CHECK (unlimited IN (0, 1)),
        unlimited_possible INTEGER NOT NULL
          CHECK (unlimited_possible IN (0, 1)),
        full_time INTEGER NOT NULL
          CHECK (full_time IN (0, 1)),
        drivers_license INTEGER NOT NULL
          CHECK (drivers_license IN (0, 1)),
        date_added TEXT NOT NULL
          CHECK (
            date_added GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(date_added) IS NOT NULL
          ),
        date_apply_start TEXT NOT NULL
          CHECK (
            date_apply_start GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(date_apply_start) IS NOT NULL
          ),
        date_apply_end TEXT NOT NULL
          CHECK (
            date_apply_end GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(date_apply_end) IS NOT NULL
          ),
        employer TEXT NOT NULL
      )
    """

  def delete_expired_jobs(self) -> None:
    """
    Deletes jobs from database whose application deadline is yesterdar or older.
    """
    today = datetime.datetime.today()
    try:
      query = (
        "DELETE FROM jobs "
        "WHERE date(date_apply_end) < date(?)"
      )
      self._cur.execute(query, (today,))
      self._cur.execute("SELECT changes()")
      self._conn.commit()
    except sqlite3.OperationalError as error:
      logger.exception(f'Failed to delete expired jobs.\nError: {error}')
      return
    rowcount = self._cur.fetchone()[0]
    logger.info(f'Deleted {rowcount} expired jobs')
  
  def delete_removed_jobs(self, jobs: list[Job]) -> None:
    """
    Deletes those jobs from the database whose application deadline hasn't
    expired yet, but are no longer available because they were manually removed
    before the expiration date.
    """

    job_ids = tuple(job.id for job in jobs)
    placeholders = ','.join(['?'] * len(job_ids))
    query = f"DELETE FROM jobs WHERE id NOT IN ({placeholders})"
    try:
      self._cur.execute(query, job_ids)
      self._cur.execute("SELECT changes()")
      self._conn.commit()
    except sqlite3.OperationalError as error:
      logger.exception(f'Failed to delete removed jobs.\nError: {error}')
      return
    rowcount = self._cur.fetchone()[0]
    logger.info(f'Deleted {rowcount} removed jobs')

  def pop_existing_jobs(self, jobs: list[Job]) -> list[Job]:
    """
    Takes a list of freshly scrapped Job objects and pops those that are
    already in the database and therefore require no further action.
    """
    ids = tuple(job.id for job in jobs)
    placeholders = ','.join(['?'] * len(ids))
    query = f"SELECT id FROM jobs WHERE id IN ({placeholders})"
    existing_ids = {row[0] for row in self._cur.execute(query, ids)}
    new_jobs = [job for job in jobs if job.id not in existing_ids]
    return new_jobs

  def insert_new_jobs(self, jobs: list[Job]) -> None:
    """
    Takes a list of freshly scrapped Job objects, cleaned up by the
    Database.pop_existing_jobs function, and converts those Job objects into
    database rows.
    """
    if len(jobs) == 0:
      logger.info('No new jobs to insert')
      return
    
    rows = []
    for job in jobs:
      try:
        if job.has_all_data():
          rows.append(job.export_sql_values())
      except Exception:
        logger.exception(f'Failed to export SQL values for {job}')
    if len(rows) > 0:
      self._cur.execute("SELECT COUNT(*) FROM pragma_table_info('jobs');")
      num_columns = self._cur.fetchone()[0]
      placeholders = ','.join(['?'] * num_columns)
      query = f"INSERT INTO jobs VALUES ({placeholders})"
      try:
        self._cur.executemany(query, rows)
        self._conn.commit()
        logger.info(f'Inserted {len(rows)} new jobs successfully')
      except sqlite3.IntegrityError:
        counter = 0
        for row in rows:
          try:
            self._cur.execute(query, row)
            counter += 1
          except sqlite3.IntegrityError:
            logger.exception(f'Insert row failed (Integrity Error): {row}')

        self._conn.commit()
        logger.warning(f'Inserted {counter}/{len(rows)} new jobs')
  
  def get_statistics(self) -> dict[str, int]:
    """Gets job statistics that are to be displayed on the web page."""
    row = self._cur.execute("""
        SELECT
            COUNT(*) AS total_jobs,
            SUM(LOWER(location)='slavonski brod') AS jobs_in_sb,
            SUM(unlimited=1) AS unlimited_jobs,
            SUM(unlimited_possible=1) AS unlimited_possible_jobs,
            SUM(full_time=1) AS full_time_jobs,
            SUM(drivers_license=1) AS drivers_license_jobs
        FROM jobs;
      """).fetchone()
    return dict(row)

  def select_all_jobs(self) -> list[dict[str, str | int]]:
    """Gets a list of all the jobs in the database for insertion into HTML"""
    rows = self._cur.execute("""
        SELECT * FROM jobs
        ORDER BY date_added DESC
      """).fetchall()
    jobs = [dict(row) for row in rows]
    return jobs